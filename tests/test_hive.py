# Tests for the registry hive reader, on hives written by tests/hive_fixture.py.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import struct

import pytest
from hive_fixture import REG_DWORD, build_hive, expand, key, sz

from reactos_liminal.hive import Hive, HiveError

TREE = {
	"Microsoft": key(
		{"Default": sz("x")},
		{
			"Run": key(
				{
					"Pad": sz("C:\\ReactOS\\notepad.exe /p"),
					"Path": expand("%SystemRoot%\\system32"),
					"Count": (REG_DWORD, struct.pack("<I", 7)),
				}
			),
			"App Paths": key({}, {"calc.exe": key({"": sz("C:\\calc.exe")})}),
		},
	)
}


def test_keys_are_found_by_a_path_that_ignores_case():
	hive = Hive(build_hive(TREE))
	assert hive.open_key("microsoft\\RUN") is not None
	assert hive.open_key("Microsoft\\Nothing") is None
	assert [key.name for key in hive.open_key("Microsoft").subkeys()] == ["Run", "App Paths"]


def test_values_have_a_name_a_type_and_text():
	run = Hive(build_hive(TREE)).open_key("Microsoft\\Run")
	by_name = {value.name: value for value in run.values()}
	assert by_name["Pad"].text() == "C:\\ReactOS\\notepad.exe /p"
	assert by_name["Path"].text() == "%SystemRoot%\\system32"
	assert by_name["Count"].text() == "" and by_name["Count"].data == struct.pack("<I", 7)


def test_the_default_value_has_an_empty_name():
	calc = Hive(build_hive(TREE)).open_key("Microsoft\\App Paths\\calc.exe")
	assert calc.value("").text() == "C:\\calc.exe"
	assert calc.value("missing") is None


@pytest.mark.parametrize("data", [b"", b"regf" + bytes(100), b"not a hive" * 1000])
def test_bytes_that_are_not_a_hive_are_refused(data):
	with pytest.raises(HiveError):
		Hive(data)
