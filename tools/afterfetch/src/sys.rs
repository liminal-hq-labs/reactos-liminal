// The Win32 calls afterfetch makes: ANSI entry points only, imported by name (raw-dylib), nothing newer than Windows 95.
//
// (c) Copyright 2026 Liminal HQ, Scott Morris
// SPDX-License-Identifier: Apache-2.0 OR MIT

#![allow(non_snake_case, non_camel_case_types, clippy::upper_case_acronyms)]

use core::ffi::c_void;

pub type Handle = *mut c_void;

pub const INVALID_HANDLE_VALUE: Handle = -1isize as Handle;
pub const STD_OUTPUT_HANDLE: u32 = -11i32 as u32;
pub const SM_CXSCREEN: i32 = 0;
pub const SM_CYSCREEN: i32 = 1;
pub const BITSPIXEL: i32 = 12;
pub const PLANES: i32 = 14;
pub const HKEY_LOCAL_MACHINE: usize = 0x8000_0002;
pub const KEY_QUERY_VALUE: u32 = 0x0001;
pub const ERROR_SUCCESS: i32 = 0;
pub const REG_SZ: u32 = 1;

#[repr(C)]
pub struct Coord {
	pub x: i16,
	pub y: i16,
}

#[repr(C)]
pub struct SmallRect {
	pub left: i16,
	pub top: i16,
	pub right: i16,
	pub bottom: i16,
}

#[repr(C)]
pub struct ConsoleScreenBufferInfo {
	pub size: Coord,
	pub cursor_position: Coord,
	pub attributes: u16,
	pub window: SmallRect,
	pub maximum_window_size: Coord,
}

#[repr(C)]
pub struct OsVersionInfoA {
	pub size: u32,
	pub major: u32,
	pub minor: u32,
	pub build: u32,
	pub platform: u32,
	pub service_pack: [u8; 128],
}

#[repr(C)]
pub struct MemoryStatus {
	pub length: u32,
	pub memory_load: u32,
	pub total_phys: u32,
	pub avail_phys: u32,
	pub total_page_file: u32,
	pub avail_page_file: u32,
	pub total_virtual: u32,
	pub avail_virtual: u32,
}

#[repr(C)]
pub struct SystemInfo {
	pub processor_architecture: u16,
	pub reserved: u16,
	pub page_size: u32,
	pub minimum_application_address: usize,
	pub maximum_application_address: usize,
	pub active_processor_mask: usize,
	pub number_of_processors: u32,
	pub processor_type: u32,
	pub allocation_granularity: u32,
	pub processor_level: u16,
	pub processor_revision: u16,
}

#[link(name = "kernel32", kind = "raw-dylib", import_name_type = "undecorated")]
unsafe extern "system" {
	pub fn ExitProcess(code: u32) -> !;
	pub fn GetStdHandle(which: u32) -> Handle;
	pub fn GetConsoleScreenBufferInfo(console: Handle, info: *mut ConsoleScreenBufferInfo) -> i32;
	pub fn SetConsoleTextAttribute(console: Handle, attributes: u16) -> i32;
	pub fn WriteConsoleA(console: Handle, text: *const u8, count: u32, written: *mut u32, reserved: *const c_void) -> i32;
	pub fn WriteFile(file: Handle, data: *const u8, count: u32, written: *mut u32, overlapped: *mut c_void) -> i32;
	pub fn GetComputerNameA(name: *mut u8, size: *mut u32) -> i32;
	pub fn GetVersionExA(info: *mut OsVersionInfoA) -> i32;
	pub fn GetSystemInfo(info: *mut SystemInfo);
	pub fn GetTickCount() -> u32;
	pub fn GlobalMemoryStatus(status: *mut MemoryStatus);
	pub fn GetEnvironmentVariableA(name: *const u8, value: *mut u8, size: u32) -> u32;
}

#[link(name = "advapi32", kind = "raw-dylib", import_name_type = "undecorated")]
unsafe extern "system" {
	pub fn GetUserNameA(name: *mut u8, size: *mut u32) -> i32;
	pub fn RegOpenKeyExA(key: usize, sub_key: *const u8, options: u32, access: u32, result: *mut usize) -> i32;
	pub fn RegQueryValueExA(
		key: usize,
		name: *const u8,
		reserved: *mut u32,
		kind: *mut u32,
		data: *mut u8,
		size: *mut u32,
	) -> i32;
	pub fn RegCloseKey(key: usize) -> i32;
}

#[link(name = "user32", kind = "raw-dylib", import_name_type = "undecorated")]
unsafe extern "system" {
	pub fn GetSystemMetrics(index: i32) -> i32;
	pub fn GetDC(window: Handle) -> Handle;
	pub fn ReleaseDC(window: Handle, dc: Handle) -> i32;
}

#[link(name = "gdi32", kind = "raw-dylib", import_name_type = "undecorated")]
unsafe extern "system" {
	pub fn GetDeviceCaps(dc: Handle, index: i32) -> i32;
}
