// afterfetch.exe: an Afterglow sunset and a few facts about this system, in the console's own colours.
//
// A Win32 console program for ReactOS and Windows 95 and later, `no_std` and `no_main` so that neither Rust's standard library nor the
// C runtime is needed. The colours are console attributes (SetConsoleTextAttribute), the facts come from native calls, and the
// console's own attributes are put back before the program ends. When the output is not a console the picture is plain ASCII.
//
// (c) Copyright 2026 Liminal HQ, Scott Morris
// SPDX-License-Identifier: Apache-2.0 OR MIT

#![no_std]
#![no_main]

mod rt;
mod sys;

use afterfetch::palette::{Tone, fill_attribute, swatch_attribute, text_attribute};
use afterfetch::render::{Info, Sink, render};
use afterfetch::text::{c_str, format_display, format_kernel, format_memory, format_os, format_shell, format_uptime};
use core::ffi::CStr;
use core::mem::MaybeUninit;
use core::ptr::{null, null_mut};
use sys::*;

/// Writes to the console with colour, or to a file or pipe as plain text.
struct Output {
	handle: Handle,
	/// The console's attributes at the start, or None when the output is not a console.
	original: Option<u16>,
	/// The attribute last set, so an unchanged one is not set again.
	current: u16,
}

impl Output {
	fn raw(&self, bytes: &[u8]) {
		let mut written = 0u32;
		// SAFETY: `bytes` is valid for its length and `written` is a live local.
		unsafe {
			if self.original.is_some() {
				WriteConsoleA(self.handle, bytes.as_ptr(), bytes.len() as u32, &mut written, null());
			} else {
				WriteFile(self.handle, bytes.as_ptr(), bytes.len() as u32, &mut written, null_mut());
			}
		}
	}

	fn set(&mut self, attribute: u16) {
		if self.original.is_some() && attribute != self.current {
			// SAFETY: the handle is the console's output.
			unsafe { SetConsoleTextAttribute(self.handle, attribute) };
			self.current = attribute;
		}
	}

	fn default_attribute(&self) -> u16 {
		self.original.unwrap_or(0)
	}
}

impl Sink for Output {
	fn is_colour(&self) -> bool {
		self.original.is_some()
	}

	fn text(&mut self, tone: Tone, bytes: &[u8]) {
		self.set(text_attribute(self.default_attribute(), tone));
		self.raw(bytes);
	}

	fn fill(&mut self, tone: Tone, count: usize) {
		const SPACES: &[u8] = b"                                ";
		const HASHES: &[u8] = b"################################";
		let (attribute, cells) = if self.original.is_some() {
			(fill_attribute(self.default_attribute(), tone), SPACES)
		} else {
			(0, HASHES)
		};
		self.set(attribute);
		self.raw(&cells[..count.min(cells.len())]);
	}

	fn swatches(&mut self, first: u8, count: u8) {
		for index in first..first + count {
			self.set(swatch_attribute(self.default_attribute(), index));
			self.raw(b"  ");
		}
	}

	fn newline(&mut self) {
		self.set(self.default_attribute());
		self.raw(b"\r\n");
	}
}

/// Fills `buffer` from a Win32 call that takes a size in and gives the length out, and returns what was written.
fn name_from(call: unsafe extern "system" fn(*mut u8, *mut u32) -> i32, buffer: &mut [u8]) -> &[u8] {
	let mut size = buffer.len() as u32;
	// SAFETY: `size` is the length of `buffer`.
	if unsafe { call(buffer.as_mut_ptr(), &mut size) } == 0 {
		return &[];
	}
	c_str(buffer)
}

/// A string value of a key under HKEY_LOCAL_MACHINE, or an empty slice.
fn registry_string<'a>(key: &CStr, name: &CStr, buffer: &'a mut [u8]) -> &'a [u8] {
	let mut handle = 0usize;
	// SAFETY: `key` and `name` end in a NUL; the buffer length is passed in `size`.
	unsafe {
		if RegOpenKeyExA(HKEY_LOCAL_MACHINE, key.as_ptr().cast(), 0, KEY_QUERY_VALUE, &mut handle) != ERROR_SUCCESS {
			return &[];
		}
		let mut size = buffer.len() as u32 - 1;
		let mut kind = 0u32;
		let status = RegQueryValueExA(
			handle,
			name.as_ptr().cast(),
			null_mut(),
			&mut kind,
			buffer.as_mut_ptr(),
			&mut size,
		);
		RegCloseKey(handle);
		if status != ERROR_SUCCESS || kind != REG_SZ {
			return &[];
		}
		buffer[size as usize] = 0;
	}
	c_str(buffer)
}

fn gather() -> Info {
	let mut info = Info::default();
	let mut scratch = [0u8; 160];

	info.user.push(name_from(GetUserNameA, &mut scratch[..64]));
	info.user.make_ascii_lowercase();
	info.host.push(name_from(GetComputerNameA, &mut scratch[..64]));
	info.host.make_ascii_lowercase();

	let mut version = MaybeUninit::<OsVersionInfoA>::zeroed();
	// SAFETY: zeroed is a valid OsVersionInfoA; the size field is set before the call.
	let version = unsafe {
		(*version.as_mut_ptr()).size = size_of::<OsVersionInfoA>() as u32;
		if GetVersionExA(version.as_mut_ptr()) != 0 {
			Some(version.assume_init())
		} else {
			None
		}
	};
	if let Some(version) = &version {
		format_kernel(
			&mut info.kernel,
			version.major,
			version.minor,
			version.build,
			c_str(&version.service_pack),
		);
	}

	// The product name and the build lab, which for ReactOS carries the release; the architecture decides the `-x86` after it.
	let mut lab = [0u8; 96];
	let key = c"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion";
	let product = registry_string(key, c"ProductName", &mut scratch);
	let build_lab = registry_string(key, c"BuildLab", &mut lab);
	let mut system = MaybeUninit::<SystemInfo>::zeroed();
	// SAFETY: the call fills the structure it is given.
	let x86 = unsafe {
		GetSystemInfo(system.as_mut_ptr());
		system.assume_init().processor_architecture == 0
	};
	format_os(&mut info.os, product, build_lab, x86);

	// SAFETY: a call with no arguments.
	format_uptime(&mut info.uptime, unsafe { GetTickCount() });

	let mut memory = MaybeUninit::<MemoryStatus>::zeroed();
	// SAFETY: the length field is set before the call; the call fills the rest.
	let memory = unsafe {
		(*memory.as_mut_ptr()).length = size_of::<MemoryStatus>() as u32;
		GlobalMemoryStatus(memory.as_mut_ptr());
		memory.assume_init()
	};
	format_memory(&mut info.memory, memory.avail_phys, memory.total_phys);

	// SAFETY: GetSystemMetrics takes no pointers; the screen DC is released after the colour depth is read.
	let (width, height, depth) = unsafe {
		let dc = GetDC(null_mut());
		let depth = if dc.is_null() {
			0
		} else {
			(GetDeviceCaps(dc, BITSPIXEL) * GetDeviceCaps(dc, PLANES)) as u32
		};
		if !dc.is_null() {
			ReleaseDC(null_mut(), dc);
		}
		(GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN), depth)
	};
	if width > 0 && height > 0 {
		format_display(&mut info.display, width as u32, height as u32, depth);
	}

	// SAFETY: the name ends in a NUL and the length passed is the buffer's.
	let length =
		unsafe { GetEnvironmentVariableA(c"COMSPEC".as_ptr().cast(), scratch.as_mut_ptr(), scratch.len() as u32) } as usize;
	let comspec = if length > 0 && length < scratch.len() {
		&scratch[..length]
	} else {
		&[][..]
	};
	format_shell(&mut info.shell, comspec);
	info
}

fn real_main() -> u32 {
	// SAFETY: the standard output handle is only used for the console and write calls below.
	let handle = unsafe { GetStdHandle(STD_OUTPUT_HANDLE) };
	let mut screen = MaybeUninit::<ConsoleScreenBufferInfo>::zeroed();
	// SAFETY: fails (and leaves the structure unused) when the handle is not a console.
	let screen = unsafe {
		if !handle.is_null() && handle != INVALID_HANDLE_VALUE && GetConsoleScreenBufferInfo(handle, screen.as_mut_ptr()) != 0 {
			Some(screen.assume_init())
		} else {
			None
		}
	};
	let mut output = Output {
		handle,
		original: screen.as_ref().map(|screen| screen.attributes),
		current: 0,
	};
	let mut columns = 80;
	if let Some(screen) = &screen {
		output.current = screen.attributes;
		columns = (i32::from(screen.window.right) - i32::from(screen.window.left) + 1).max(1) as usize;
	}
	let info = gather();
	render(&mut output, &info, columns);
	// The attributes were put back by the last newline; this is for a run cut short.
	let restore = output.default_attribute();
	output.set(restore);
	0
}

#[unsafe(no_mangle)]
pub extern "C" fn start() -> ! {
	let code = real_main();
	// SAFETY: ends the process.
	unsafe { ExitProcess(code) }
}
