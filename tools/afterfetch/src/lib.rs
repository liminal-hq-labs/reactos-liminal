// afterfetch: the pure parts of the command. The palette, the logo, the text formatting and the layout, with no Windows call in
// them, so they run under `cargo test` on the host.
//
// (c) Copyright 2026 Liminal HQ, Scott Morris
// SPDX-License-Identifier: Apache-2.0 OR MIT

#![cfg_attr(not(test), no_std)]

pub mod logo;
pub mod palette;
pub mod render;
pub mod text;
