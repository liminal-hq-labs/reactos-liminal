// The Afterglow sunset. Each row is the picture as ASCII beside a row of the same width that names the tone of every character, so
// the gradient can be read straight off the page: gold sun, orange, coral at the horizon, a rose line, then water from lilac through
// violet and periwinkle to slate.
//
// A `#` is the sun's body. On a console it is drawn as a solid cell (a space on a coloured background); on a pipe it stays a `#`.
//
// (c) Copyright 2026 Liminal HQ, Scott Morris
// SPDX-License-Identifier: Apache-2.0 OR MIT

use crate::palette::Tone;

/// One row of the picture.
pub struct Row {
	pub art: &'static str,
	/// One letter per character of `art`: g gold, o orange, c coral, r rose, l lilac, v violet, p periwinkle, s slate, space plain.
	pub tones: &'static str,
}

/// The column where the information starts, which is also the width the logo is padded to.
pub const INFO_COLUMN: usize = 42;

pub const ROWS: [Row; 12] = [
	Row {
		art: "                 .   .   .",
		tones: "                 l   l   l",
	},
	Row {
		art: "           .      \\  :  /      .",
		tones: "           l      g  g  g      l",
	},
	Row {
		art: "               .   \\ : /   .",
		tones: "               l   g g g   l",
	},
	Row {
		art: "                .:########:.",
		tones: "                gggggggggggg",
	},
	Row {
		art: "            .:##############:.",
		tones: "            gggggggggggggggggg",
	},
	Row {
		art: "           :##################:",
		tones: "           oooooooooooooooooooo",
	},
	Row {
		art: "       ====:##################:====",
		tones: "       rrrrccccccccccccccccccccrrrr",
	},
	Row {
		art: "      ----------------------------------",
		tones: "      rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr",
	},
	Row {
		art: "       ~~~~  ~~~~~~~~~  ~~~~~~~  ~~~~",
		tones: "       llll  vvvvvvvvv  lllllll  vvvv",
	},
	Row {
		art: "         ~~~~~~~  ~~~~~~~~~~  ~~~~~~",
		tones: "         vvvvvvv  pppppppppp  vvvvvv",
	},
	Row {
		art: "            ~~~~~~~~~~  ~~~~~~~~~",
		tones: "            pppppppppp  sssssssss",
	},
	Row {
		art: "               ~~~~~~~~~~~~~~",
		tones: "               ssssssssssssss",
	},
];

/// The tone a letter of a `tones` row names.
pub const fn tone_of(letter: u8) -> Tone {
	match letter {
		b'g' => Tone::Gold,
		b'o' => Tone::Orange,
		b'c' => Tone::Coral,
		b'r' => Tone::Rose,
		b'l' => Tone::Lilac,
		b'v' => Tone::Violet,
		b'p' => Tone::Periwinkle,
		b's' => Tone::Slate,
		_ => Tone::Plain,
	}
}

#[cfg(test)]
mod tests {
	use super::*;

	#[test]
	fn every_row_names_a_tone_for_each_character() {
		for (number, row) in ROWS.iter().enumerate() {
			assert_eq!(row.art.len(), row.tones.len(), "row {number}");
			assert!(row.art.is_ascii(), "row {number}");
			assert!(row.art.len() < INFO_COLUMN, "row {number} reaches the information column");
		}
	}

	#[test]
	fn only_known_letters_and_spaces_are_used() {
		for row in &ROWS {
			for letter in row.tones.bytes() {
				assert!(b" gocrlvps".contains(&letter), "unknown tone letter {}", letter as char);
			}
		}
	}

	#[test]
	fn spaces_are_plain_and_drawn_characters_are_toned() {
		for row in &ROWS {
			for (character, letter) in row.art.bytes().zip(row.tones.bytes()) {
				assert_eq!(character == b' ', letter == b' ');
			}
		}
	}

	#[test]
	fn the_sun_is_solid_and_toned_by_row() {
		let rows_with_sun: Vec<usize> = ROWS
			.iter()
			.enumerate()
			.filter(|(_, row)| row.art.contains('#'))
			.map(|(number, _)| number)
			.collect();
		assert_eq!(rows_with_sun, [3, 4, 5, 6]);
		for number in rows_with_sun {
			let row = &ROWS[number];
			for (character, letter) in row.art.bytes().zip(row.tones.bytes()) {
				if character == b'#' {
					assert_ne!(tone_of(letter), Tone::Plain);
				}
			}
		}
	}
}
