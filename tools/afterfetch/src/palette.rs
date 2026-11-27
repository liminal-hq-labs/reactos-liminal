// The colours afterfetch uses, as names for the roles they play in the picture, each mapped to one of the console's 16 colour indexes.
//
// The image sets the console's colour table from the Afterglow Dusk palette (HKCU\Console, ColorTable00 to 15), so an index here is an
// Afterglow colour on the image and whatever the user's own table holds elsewhere. The indexes follow the order of the table, which
// reads: 0 navy, 1 periwinkle, 2 green, 3 teal, 4 rose, 5 violet, 6 orange, 7 text, 8 slate, then the bright set 9 to 15.
//
// (c) Copyright 2026 Liminal HQ, Scott Morris
// SPDX-License-Identifier: Apache-2.0 OR MIT

/// A role in the picture. `Plain` is the console's own foreground and background.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tone {
	Plain,
	/// The sun: pale gold.
	Gold,
	/// The lower sun.
	Orange,
	/// The sun at the horizon.
	Coral,
	/// The horizon line.
	Rose,
	/// The sky's light end and the water just under the horizon.
	Lilac,
	/// The middle of the water.
	Violet,
	/// The deeper water.
	Periwinkle,
	/// The darkest water, and quiet text.
	Slate,
}

impl Tone {
	/// The console colour index (0 to 15) this tone is drawn with, or None for `Plain`.
	pub const fn index(self) -> Option<u8> {
		match self {
			Tone::Plain => None,
			Tone::Gold => Some(14),
			Tone::Orange => Some(6),
			Tone::Coral => Some(12),
			Tone::Rose => Some(4),
			Tone::Lilac => Some(13),
			Tone::Violet => Some(5),
			Tone::Periwinkle => Some(1),
			Tone::Slate => Some(8),
		}
	}
}

/// The console attribute for text in `tone` over the console's own background: `default` is the attribute the console had at the start.
/// Bits above the colour nibbles (such as reverse video) are kept.
pub const fn text_attribute(default: u16, tone: Tone) -> u16 {
	match tone.index() {
		None => default,
		Some(index) => (default & !0x000F) | index as u16,
	}
}

/// The console attribute for a filled cell in `tone`: a space on a background of that colour.
pub const fn fill_attribute(default: u16, tone: Tone) -> u16 {
	match tone.index() {
		None => default,
		Some(index) => (default & !0x00F0) | ((index as u16) << 4),
	}
}

/// The attribute of a swatch cell: console colour `index` as the background.
pub const fn swatch_attribute(default: u16, index: u8) -> u16 {
	(default & !0x00F0) | (((index & 0x0F) as u16) << 4)
}
