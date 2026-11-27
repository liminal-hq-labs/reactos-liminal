// The layout: the logo on the left, the facts on the right. It writes through a `Sink`, which the program backs with the console
// and the tests back with a string, so the layout and the colour choices are tested without a console.
//
// (c) Copyright 2026 Liminal HQ, Scott Morris
// SPDX-License-Identifier: Apache-2.0 OR MIT

use crate::logo::{INFO_COLUMN, ROWS, tone_of};
use crate::palette::Tone;
use crate::text::Buf;

/// The facts, each as text. An empty one is printed as a dash.
#[derive(Default)]
pub struct Info {
	pub user: Buf<32>,
	pub host: Buf<32>,
	pub os: Buf<48>,
	pub kernel: Buf<48>,
	pub uptime: Buf<32>,
	pub memory: Buf<48>,
	pub display: Buf<32>,
	pub shell: Buf<32>,
}

/// Where the output goes.
pub trait Sink {
	/// True when tones are drawn. False for a pipe or a file, where the picture is plain ASCII and the colour swatches are left out.
	fn is_colour(&self) -> bool;
	/// Text in a tone over the console's own background.
	fn text(&mut self, tone: Tone, bytes: &[u8]);
	/// `count` solid cells in a tone (a `#` where colour is off).
	fn fill(&mut self, tone: Tone, count: usize);
	/// Two-cell swatches of the console colours `first` up to (not including) `first + count`.
	fn swatches(&mut self, first: u8, count: u8);
	/// Ends the line, with the console's own attributes restored first so a scroll does not paint the new line.
	fn newline(&mut self);
}

/// The width of the label column on the right: `Display:  `.
const LABEL_WIDTH: usize = 10;

/// The information rows: the title, a rule, six labelled facts, a gap and two rows of colour swatches (slots 0 to 10).
const INFO_ROWS: usize = 11;

/// Writes the whole picture to `sink` for a console `columns` wide. A console too narrow for both columns gets the facts alone.
pub fn render(sink: &mut impl Sink, info: &Info, columns: usize) {
	let side_by_side = columns >= INFO_COLUMN + LABEL_WIDTH + 24;
	let left = if side_by_side { INFO_COLUMN } else { 0 };
	let room = columns.saturating_sub(left + LABEL_WIDTH + 1);
	for row in 0..if side_by_side { ROWS.len() } else { INFO_ROWS } {
		// With the logo, the facts start on its second row; without it, at the top.
		let slot = if side_by_side { row.checked_sub(1) } else { Some(row) }
			.filter(|slot| *slot < INFO_ROWS)
			.filter(|slot| *slot != 8 && (*slot < 9 || sink.is_colour()));
		if side_by_side {
			let written = logo_row(sink, row);
			if slot.is_some() {
				pad(sink, INFO_COLUMN - written);
			}
		}
		if let Some(slot) = slot {
			info_row(sink, info, slot, room);
		}
		sink.newline();
	}
}

fn logo_row(sink: &mut impl Sink, row: usize) -> usize {
	let art = ROWS[row].art.as_bytes();
	let tones = ROWS[row].tones.as_bytes();
	let mut at = 0;
	while at < art.len() {
		let tone = tone_of(tones[at]);
		let solid = art[at] == b'#';
		let mut end = at;
		while end < art.len() && tone_of(tones[end]) == tone && (art[end] == b'#') == solid {
			end += 1;
		}
		if solid {
			sink.fill(tone, end - at);
		} else {
			sink.text(tone, &art[at..end]);
		}
		at = end;
	}
	art.len()
}

fn pad(sink: &mut impl Sink, count: usize) {
	const SPACES: &[u8] = b"                                                                ";
	let mut left = count;
	while left > 0 {
		let take = left.min(SPACES.len());
		sink.text(Tone::Plain, &SPACES[..take]);
		left -= take;
	}
}

fn dashes(sink: &mut impl Sink, tone: Tone, count: usize) {
	const DASHES: &[u8] = b"--------------------------------------------------------------------------------";
	sink.text(tone, &DASHES[..count.min(DASHES.len())]);
}

fn value(sink: &mut impl Sink, bytes: &[u8], room: usize) {
	if bytes.is_empty() {
		sink.text(Tone::Plain, b"-");
	} else {
		sink.text(Tone::Plain, &bytes[..bytes.len().min(room)]);
	}
}

fn info_row(sink: &mut impl Sink, info: &Info, slot: usize, room: usize) {
	match slot {
		0 => {
			let (user, host) = (info.user.as_bytes(), info.host.as_bytes());
			sink.text(Tone::Gold, if user.is_empty() { b"-" } else { user });
			sink.text(Tone::Slate, b"@");
			sink.text(Tone::Lilac, if host.is_empty() { b"-" } else { host });
		}
		1 => dashes(sink, Tone::Slate, info.user.len().max(1) + 1 + info.host.len().max(1)),
		2 => labelled_row(sink, b"OS:", Tone::Gold, info.os.as_bytes(), room),
		3 => labelled_row(sink, b"Kernel:", Tone::Orange, info.kernel.as_bytes(), room),
		4 => labelled_row(sink, b"Uptime:", Tone::Coral, info.uptime.as_bytes(), room),
		5 => labelled_row(sink, b"Memory:", Tone::Rose, info.memory.as_bytes(), room),
		6 => labelled_row(sink, b"Display:", Tone::Lilac, info.display.as_bytes(), room),
		7 => labelled_row(sink, b"Shell:", Tone::Violet, info.shell.as_bytes(), room),
		9 if sink.is_colour() => sink.swatches(0, 8),
		10 if sink.is_colour() => sink.swatches(8, 8),
		_ => {}
	}
}

fn labelled_row(sink: &mut impl Sink, label: &[u8], tone: Tone, bytes: &[u8], room: usize) {
	sink.text(tone, label);
	pad(sink, LABEL_WIDTH.saturating_sub(label.len()));
	value(sink, bytes, room);
}

#[cfg(test)]
mod tests {
	use super::*;
	use crate::palette::{fill_attribute, swatch_attribute, text_attribute};

	/// Collects the output as plain text, and the tone of every character as a parallel string of letters.
	struct Capture {
		colour: bool,
		plain: String,
		tones: String,
	}

	fn letter(tone: Tone) -> char {
		match tone {
			Tone::Plain => ' ',
			Tone::Gold => 'g',
			Tone::Orange => 'o',
			Tone::Coral => 'c',
			Tone::Rose => 'r',
			Tone::Lilac => 'l',
			Tone::Violet => 'v',
			Tone::Periwinkle => 'p',
			Tone::Slate => 's',
		}
	}

	impl Sink for Capture {
		fn is_colour(&self) -> bool {
			self.colour
		}
		fn text(&mut self, tone: Tone, bytes: &[u8]) {
			for &byte in bytes {
				self.plain.push(byte as char);
				self.tones.push(letter(tone));
			}
		}
		fn fill(&mut self, tone: Tone, count: usize) {
			for _ in 0..count {
				self.plain.push(if self.colour { '\u{2588}' } else { '#' });
				self.tones.push(letter(tone));
			}
		}
		fn swatches(&mut self, first: u8, count: u8) {
			for index in first..first + count {
				self.plain.push_str("[]");
				self.tones.push_str(if index < 10 { "0" } else { "1" });
				self.tones.push_str("x");
			}
		}
		fn newline(&mut self) {
			self.plain.push('\n');
			self.tones.push('\n');
		}
	}

	fn sample() -> Info {
		let mut info = Info::default();
		info.user.push(b"administrator");
		info.host.push(b"reactos");
		info.os.push(b"ReactOS 0.4.16-x86");
		info.kernel.push(b"NT 5.2.3790 SP3");
		info.uptime.push(b"0d 0h 1m");
		info.memory.push(b"387 MB free of 511 MB");
		info.display.push(b"1024 x 768, 32-bit");
		info.shell.push(b"cmd.exe");
		info
	}

	fn run(colour: bool, columns: usize, info: &Info) -> (Vec<String>, Vec<String>) {
		let mut capture = Capture {
			colour,
			plain: String::new(),
			tones: String::new(),
		};
		render(&mut capture, info, columns);
		(
			capture.plain.lines().map(String::from).collect(),
			capture.tones.lines().map(String::from).collect(),
		)
	}

	#[test]
	fn plain_output_is_the_ascii_picture_beside_the_facts() {
		let (lines, _) = run(false, 80, &sample());
		assert_eq!(lines.len(), 12);
		let beside = |row: usize, fact: &str| format!("{:<width$}{fact}", ROWS[row].art, width = INFO_COLUMN);
		assert_eq!(lines[0], ROWS[0].art);
		assert_eq!(lines[1], beside(1, "administrator@reactos"));
		assert_eq!(lines[2], beside(2, "---------------------"));
		assert_eq!(lines[3], beside(3, "OS:       ReactOS 0.4.16-x86"));
		assert_eq!(lines[4], beside(4, "Kernel:   NT 5.2.3790 SP3"));
		assert_eq!(lines[5], beside(5, "Uptime:   0d 0h 1m"));
		assert_eq!(lines[6], beside(6, "Memory:   387 MB free of 511 MB"));
		assert_eq!(lines[7], beside(7, "Display:  1024 x 768, 32-bit"));
		assert_eq!(lines[8], beside(8, "Shell:    cmd.exe"));
		// No swatches on a pipe: the last rows hold the water alone.
		assert_eq!(lines[9], ROWS[9].art);
		assert_eq!(lines[10], ROWS[10].art);
		assert_eq!(lines[11], ROWS[11].art);
	}

	#[test]
	fn facts_start_in_one_column() {
		let (lines, _) = run(false, 80, &sample());
		for (row, wanted) in [
			(1, "administrator@reactos"),
			(2, "---------------------"),
			(3, "OS:"),
			(6, "Memory:"),
			(8, "Shell:"),
		] {
			assert_eq!(lines[row].find(wanted), Some(INFO_COLUMN), "row {row}");
		}
		for line in &lines {
			assert!(line.len() < 80, "a line of {} characters would wrap: {line}", line.len());
		}
	}

	#[test]
	fn the_sunset_runs_from_gold_through_dusk_to_slate() {
		let (_, tones) = run(true, 80, &sample());
		// The logo's half of each row (before the information column), top to bottom.
		let first_tone = |row: usize, wanted: char| tones[row].chars().take(INFO_COLUMN).any(|tone| tone == wanted);
		assert!(first_tone(3, 'g') && first_tone(4, 'g'), "the sun's top is gold");
		assert!(first_tone(5, 'o'), "then orange");
		assert!(first_tone(6, 'c'), "coral at the horizon");
		assert!(first_tone(7, 'r'), "a rose horizon line");
		assert!(
			first_tone(8, 'l') && first_tone(9, 'v') && first_tone(10, 'p') && first_tone(11, 's'),
			"water darkens downwards"
		);
	}

	#[test]
	fn colour_output_draws_the_sun_solid_and_adds_the_swatches() {
		let (lines, _) = run(true, 80, &sample());
		assert!(lines[3].contains("\u{2588}\u{2588}"));
		assert!(!lines[3].contains('#'));
		assert!(lines[10].contains("[][][][][][][][]"));
		assert!(lines[11].contains("[][][][][][][][]"));
		assert_eq!(lines[9], ROWS[9].art, "the gap row has no swatches");
	}

	#[test]
	fn a_missing_fact_is_a_dash() {
		let (lines, _) = run(false, 80, &Info::default());
		assert!(lines[1].ends_with("-@-"));
		assert!(lines[3].ends_with("OS:       -"));
		assert!(lines[8].ends_with("Shell:    -"));
	}

	#[test]
	fn a_long_value_is_cut_to_the_console_width() {
		let mut info = sample();
		info.os.clear();
		info.os.push(b"a very long operating system name that cannot fit");
		let (lines, _) = run(false, 80, &info);
		assert!(lines[3].len() <= 79);
	}

	#[test]
	fn a_narrow_console_gets_the_facts_without_the_logo() {
		let (lines, _) = run(false, 40, &sample());
		assert_eq!(lines[0], "administrator@reactos");
		assert_eq!(lines[2], "OS:       ReactOS 0.4.16-x86");
		assert!(lines.iter().all(|line| !line.contains('~')));
	}

	#[test]
	fn tones_map_to_console_colours_the_image_sets() {
		// The Afterglow Dusk console table, as the image writes it (desktop/install/afterglow-original.reg in Afterglow), as 0xRRGGBB.
		const DUSK: [u32; 16] = [
			0x0a1230, 0x7f95f2, 0x86cf9a, 0x62c6d6, 0xf43f5e, 0xc98be6, 0xffaa40, 0xe9e2d8, 0x7c8796, 0xa9b8ff, 0xb0efc0,
			0x98e6f0, 0xf995a6, 0xe4b8f8, 0xffd08e, 0xfff7ea,
		];
		let wanted = [
			(Tone::Gold, 0xffd08e),
			(Tone::Orange, 0xffaa40),
			(Tone::Coral, 0xf995a6),
			(Tone::Rose, 0xf43f5e),
			(Tone::Lilac, 0xe4b8f8),
			(Tone::Violet, 0xc98be6),
			(Tone::Periwinkle, 0x7f95f2),
			(Tone::Slate, 0x7c8796),
		];
		for (tone, colour) in wanted {
			assert_eq!(DUSK[tone.index().unwrap() as usize], colour, "{tone:?}");
		}
		assert_eq!(Tone::Plain.index(), None);
	}

	#[test]
	fn attributes_keep_the_console_background() {
		// A console of colour 7 on colour 0 (0x07), and of colour 0 on colour 15 (0xF0, the light scheme).
		assert_eq!(text_attribute(0x07, Tone::Gold), 0x0e);
		assert_eq!(text_attribute(0x07, Tone::Plain), 0x07);
		assert_eq!(text_attribute(0xF0, Tone::Rose), 0xF4);
		assert_eq!(fill_attribute(0x07, Tone::Gold), 0xe7);
		assert_eq!(fill_attribute(0x07, Tone::Plain), 0x07);
		assert_eq!(swatch_attribute(0x07, 9), 0x97);
		// Bits above the colours, such as reverse video, are not disturbed.
		assert_eq!(text_attribute(0x4007, Tone::Violet), 0x4005);
	}
}
