@echo off
rem fastfetch: runs afterfetch, so the name people type at a command prompt works. Arguments are passed through.
rem Names the program with its extension so the shim never finds itself.
rem
rem (c) Copyright 2026 Liminal HQ, Scott Morris
rem SPDX-License-Identifier: Apache-2.0 OR MIT
afterfetch.exe %*
