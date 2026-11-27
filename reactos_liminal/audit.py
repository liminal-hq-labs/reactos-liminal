# Audit the shortcuts and registry entries of a built image for targets that are not on the disk: every .lnk with the file it runs,
# the Run keys, App Paths, Uninstall, control panel applets (Cpls), the Winlogon shell and notification DLLs, file association
# commands, the font list, and desktop.ini files.
# Read only: the image is read through mtools, the hives are parsed in memory.
#
# (c) Copyright 2026 Liminal HQ, Scott Morris
# SPDX-License-Identifier: Apache-2.0 OR MIT
import re
from dataclasses import dataclass, field

from .hive import REG_EXPAND_SZ, REG_SZ, Hive, HiveError, Key
from .lnk import LinkError, read_lnk
from .mtools import FatImage

DEAD = "dead"
ICON_MISSING = "icon missing"
OK = "ok"
UNCHECKED = "unchecked"

# What the guest's environment variables are, so a link written with `%SystemRoot%` can be checked on the host.
ENVIRONMENT = {
	"systemroot": "C:\\ReactOS",
	"windir": "C:\\ReactOS",
	"systemdrive": "C:",
	"programfiles": "C:\\Program Files",
	"commonprogramfiles": "C:\\Program Files\\Common Files",
	"allusersprofile": "C:\\Documents and Settings\\All Users",
	"comspec": "C:\\ReactOS\\system32\\cmd.exe",
	"homedrive": "C:",
}
SEARCH_FOLDERS = ("ReactOS/system32", "ReactOS")  # where a bare file name is found, as the guest's PATH finds it
USER_PROFILES = ("Default User", "Administrator", "NetworkService", "All Users")
SHORTCUT_FOLDERS = ("start menu", "desktop", "quick launch")  # the folders whose links a user sees

BLOCKING_KINDS = ("shortcut", "run", "winlogon", "applet")
RUN_KEYS = ("Run", "RunOnce", "RunServices", "RunServicesOnce")
EXECUTABLE_END = re.compile(r"\.(exe|com|bat|cmd|scr|cpl|msc|dll)\b", re.IGNORECASE)
ENVIRONMENT_USE = re.compile(r"%([^%]+)%")


@dataclass(frozen=True)
class Finding:
	"""One entry that names a file. `status` is `ok`, `dead` (the file is not on the disk), `icon missing` (the entry's file is there
	but its icon file is not) or `unchecked` (it names nothing the disk can hold: a virtual folder, an unknown variable)."""

	kind: str  # shortcut, run, app path, uninstall, applet, winlogon, association, font, desktop.ini
	where: str  # the link's path on the disk, or the registry key and value
	target: str  # what it names, as the entry writes it
	status: str
	note: str = ""


@dataclass
class AuditReport:
	findings: list[Finding] = field(default_factory=list)
	files: int = 0

	def with_status(self, status: str) -> list[Finding]:
		return [finding for finding in self.findings if finding.status == status]

	@property
	def dead(self) -> list[Finding]:
		return self.with_status(DEAD)

	def blocking(self, strict: bool = False) -> list[Finding]:
		"""The dead entries that fail the audit: what a user sees in a menu or on the desktop, what runs at logon and the control panel's
		applets. With `strict`, every dead entry, including file types, App Paths, uninstall entries and fonts."""
		return [finding for finding in self.dead if strict or finding.kind in BLOCKING_KINDS]

	def render(self, title: str = "Shortcut and registry audit") -> str:
		"""The report as Markdown: counts, then the dead entries, then the missing icons, then everything else by kind."""
		lines = [f"# {title}", ""]
		counts = {status: len(self.with_status(status)) for status in (OK, DEAD, ICON_MISSING, UNCHECKED)}
		lines.append(
			f"{len(self.findings)} entries on a disk of {self.files} files: **{counts[OK]} ok**, **{counts[DEAD]} dead**, "
			f"{counts[ICON_MISSING]} with a missing icon file, {counts[UNCHECKED]} unchecked."
		)
		for status, heading in ((DEAD, "Dead entries"), (ICON_MISSING, "Missing icon files")):
			found = self.with_status(status)
			lines += ["", f"## {heading}", ""]
			if not found:
				lines.append("None.")
				continue
			lines += ["| Kind | Where | Target | Note |", "|---|---|---|---|"]
			lines += [f"| {item.kind} | `{item.where}` | `{item.target}` | {item.note} |" for item in found]
		lines += ["", "## Entries checked, by kind", "", "| Kind | Ok | Dead | Icon missing | Unchecked |", "|---|---:|---:|---:|---:|"]
		for kind in sorted({finding.kind for finding in self.findings}):
			row = [sum(1 for f in self.findings if f.kind == kind and f.status == status) for status in (OK, DEAD, ICON_MISSING, UNCHECKED)]
			lines.append(f"| {kind} | {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
		return "\n".join(lines) + "\n"


class Disk:
	"""The files of an image, for existence checks that ignore case, as FAT does."""

	def __init__(self, image: FatImage):
		self.image = image
		self.paths = image.list_files()
		self.known = {path.rstrip("/").lower() for path in self.paths}

	def exists(self, path: str) -> bool:
		return path.replace("\\", "/").strip("/").lower() in self.known

	def resolve(self, text: str) -> tuple[str, str]:
		"""(status, note) for a path as the guest writes it: `%SystemRoot%\\system32\\x.dll`, `C:\\Program Files\\y.exe` or a bare name."""
		text = text.strip().strip('"')
		if not text:
			return UNCHECKED, "empty"
		unknown = []

		def expand(match: re.Match) -> str:
			value = ENVIRONMENT.get(match.group(1).lower())
			if value is None:
				unknown.append(match.group(0))
				return match.group(0)
			return value

		text = ENVIRONMENT_USE.sub(expand, text)
		if unknown:
			return UNCHECKED, f"uses {unknown[0]}, which is not fixed"
		if "://" in text or text.startswith("\\\\"):
			return UNCHECKED, "not a local file"
		match = re.match(r"^([A-Za-z]):[\\/]?(.*)$", text)
		if match:
			if match.group(1).upper() != "C":
				return UNCHECKED, f"on drive {match.group(1).upper()}:"
			return (OK, "") if self.exists(match.group(2)) else (DEAD, "")
		relative = text.replace("\\", "/").lstrip("/")
		if "/" in relative:
			return (OK, "") if self.exists(relative) else (DEAD, "")
		for folder in SEARCH_FOLDERS:
			if self.exists(f"{folder}/{relative}"):
				return OK, ""
		return DEAD, ""


def command_target(command: str) -> str:
	"""The file a command line runs: the quoted first word, or the text up to the first executable extension, or the first word."""
	command = command.strip()
	if command.startswith('"'):
		end = command.find('"', 1)
		return command[1:end] if end > 0 else command[1:]
	match = EXECUTABLE_END.search(command)
	if match:
		return command[: match.end()]
	return command.split(None, 1)[0] if command else ""


def _is_menu_shortcut(path: str) -> bool:
	return any(folder in path.lower().split("/") for folder in SHORTCUT_FOLDERS)


def audit_shortcuts(disk: Disk, report: AuditReport) -> None:
	for path in disk.paths:
		if not path.lower().endswith(".lnk"):
			continue
		try:
			link = read_lnk(disk.image.read(path))
		except LinkError as error:
			report.findings.append(Finding("shortcut", path, "", UNCHECKED, str(error)))
			continue
		kind = "shortcut" if _is_menu_shortcut(path) else "shortcut (elsewhere)"
		if link.target:
			status, note = disk.resolve(link.target)
			report.findings.append(Finding(kind, path, link.target, status, note))
		else:
			report.findings.append(Finding(kind, path, "", UNCHECKED, "no file path in the link"))
			status = UNCHECKED
		if link.icon and status != DEAD and disk.resolve(link.icon)[0] == DEAD:
			report.findings.append(Finding(kind, path, link.icon, ICON_MISSING, "the icon file"))


def _registry_text(key: Key, name: str) -> str:
	value = key.value(name)
	return value.text() if value is not None and value.kind in (REG_SZ, REG_EXPAND_SZ) else ""


def _check_value(disk: Disk, report: AuditReport, kind: str, where: str, command: str, whole_command: bool = True) -> None:
	if not command:
		return
	target = command_target(command) if whole_command else command
	if target.startswith("%") and target[1:2] in ("1", "*", "l", "L"):
		report.findings.append(Finding(kind, where, target, UNCHECKED, "the file the user opens"))
		return
	status, note = disk.resolve(target)
	report.findings.append(Finding(kind, where, target, status, note))


def audit_hive(disk: Disk, report: AuditReport, label: str, hive: Hive, prefix: str) -> None:
	"""The keys of one hive that run or load a file. `prefix` is `Software\\` for a user hive, empty for the machine's SOFTWARE hive."""
	current = f"{prefix}Microsoft\\Windows\\CurrentVersion"
	for name in RUN_KEYS:
		key = hive.open_key(f"{current}\\{name}")
		for value in key.values() if key else []:
			_check_value(disk, report, "run", f"{label}\\{current}\\{name}\\{value.name}", value.text())
	paths = hive.open_key(f"{current}\\App Paths")
	for app in paths.subkeys() if paths else []:
		_check_value(disk, report, "app path", f"{label}\\{current}\\App Paths\\{app.name}", _registry_text(app, ""))
	uninstall = hive.open_key(f"{current}\\Uninstall")
	for program in uninstall.subkeys() if uninstall else []:
		where = f"{label}\\{current}\\Uninstall\\{program.name}"
		_check_value(disk, report, "uninstall", where + "\\UninstallString", _registry_text(program, "UninstallString"))
		icon = _registry_text(program, "DisplayIcon").split(",", 1)[0]
		_check_value(disk, report, "uninstall", where + "\\DisplayIcon", icon, whole_command=False)
	applets = hive.open_key(f"{current}\\Control Panel\\Cpls")
	for value in applets.values() if applets else []:
		_check_value(disk, report, "applet", f"{label}\\{current}\\Control Panel\\Cpls\\{value.name}", value.text(), whole_command=False)
	winlogon = hive.open_key(f"{prefix}Microsoft\\Windows NT\\CurrentVersion\\Winlogon")
	if winlogon is not None:
		where = f"{label}\\{prefix}Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
		for name in ("Shell", "ConsoleShell", "GinaDLL"):
			_check_value(disk, report, "winlogon", f"{where}\\{name}", _registry_text(winlogon, name))
		for program in _registry_text(winlogon, "Userinit").split(","):
			_check_value(disk, report, "winlogon", f"{where}\\Userinit", program.strip())
		notify = winlogon.subkey("Notify")
		for package in notify.subkeys() if notify else []:
			_check_value(disk, report, "winlogon", f"{where}\\Notify\\{package.name}\\DllName", _registry_text(package, "DllName"))


def _audit_verbs(disk: Disk, report: AuditReport, label: str, owner: Key, trail: str) -> None:
	shell = owner.subkey("shell")
	for verb in shell.subkeys() if shell else []:
		command = verb.subkey("command")
		if command is not None:
			_check_value(disk, report, "association", f"{label}\\{trail}\\shell\\{verb.name}\\command", _registry_text(command, ""))


def audit_software_only(disk: Disk, report: AuditReport, hive: Hive) -> None:
	"""What only the machine hive holds: the commands of file types and programs, and the font list."""
	label = "HKLM\\SOFTWARE"
	classes = hive.open_key("Classes")
	for owner in classes.subkeys() if classes else []:
		if owner.name.lower() == "applications":
			for program in owner.subkeys():
				_audit_verbs(disk, report, label, program, f"Classes\\Applications\\{program.name}")
		else:
			_audit_verbs(disk, report, label, owner, f"Classes\\{owner.name}")
	fonts = hive.open_key("Microsoft\\Windows NT\\CurrentVersion\\Fonts")
	for value in fonts.values() if fonts else []:
		name = value.text()
		path = name if ":" in name or "\\" in name else f"C:\\ReactOS\\Fonts\\{name}"
		status, note = disk.resolve(path)
		report.findings.append(Finding("font", f"{label}\\Microsoft\\Windows NT\\CurrentVersion\\Fonts\\{value.name}", name, status, note))


def audit_registry(disk: Disk, report: AuditReport) -> None:
	"""Read each hive on the disk that a launch can come from: SOFTWARE, the default user's and each profile's NTUSER.DAT."""
	hives = [
		("HKLM\\SOFTWARE", "ReactOS/system32/config/SOFTWARE", ""),
		("HKU\\.DEFAULT", "ReactOS/system32/config/DEFAULT", "Software\\"),
	]
	for profile in USER_PROFILES:
		hives.append((f"HKU\\{profile}", f"Documents and Settings/{profile}/ntuser.dat", "Software\\"))
	hives.append(("HKU\\systemprofile", "ReactOS/system32/config/systemprofile/ntuser.dat", "Software\\"))
	for label, path, prefix in hives:
		if not disk.exists(path):
			continue
		try:
			hive = Hive(disk.image.read(path))
			audit_hive(disk, report, label, hive, prefix)
			if label == "HKLM\\SOFTWARE":
				audit_software_only(disk, report, hive)
		except HiveError as error:
			report.findings.append(Finding("registry", path, "", UNCHECKED, f"cannot read the hive: {error}"))


def parse_ini(text: str) -> dict[str, str]:
	"""The `key=value` pairs of a desktop.ini, keys lower-cased, sections ignored."""
	pairs = {}
	for line in text.splitlines():
		key, separator, value = line.strip().partition("=")
		if separator:
			pairs[key.strip().lower()] = value.strip()
	return pairs


def audit_desktop_ini(disk: Disk, report: AuditReport) -> None:
	for path in disk.paths:
		if not path.lower().endswith("/desktop.ini") and path.lower() != "desktop.ini":
			continue
		raw = disk.image.read(path)
		text = raw.decode("utf-16", errors="replace") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("latin-1")
		pairs = parse_ini(text)
		for key in ("iconfile", "iconresource", "localizedresourcename"):
			reference = pairs.get(key, "").lstrip("@")
			file_name = reference.split(",", 1)[0]
			if file_name:
				status, note = disk.resolve(file_name)
				report.findings.append(Finding("desktop.ini", f"{path} {key}", file_name, status, note))


def audit_image(image: FatImage) -> AuditReport:
	"""Check every shortcut, registry launch point and desktop.ini on the image."""
	disk = Disk(image)
	report = AuditReport(files=len(disk.paths))
	audit_shortcuts(disk, report)
	audit_registry(disk, report)
	audit_desktop_ini(disk, report)
	return report
