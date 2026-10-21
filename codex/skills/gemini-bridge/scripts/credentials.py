"""Device-local OS credential storage. No plaintext or environment fallback."""
import ctypes
import getpass
import sys

SERVICE = b"codex-gemini-bridge"
ACCOUNT = b"google-api-key"
WINDOWS_TARGET = "CodexGeminiBridge/GoogleAPIKey"


class CredentialError(RuntimeError):
    pass


class MacStore:
    def __init__(self):
        self.lib = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        self.cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]
        self.lib.SecKeychainFindGenericPassword.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32,
            ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
        self.lib.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        self.lib.SecKeychainAddGenericPassword.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32,
            ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_void_p]
        self.lib.SecKeychainAddGenericPassword.restype = ctypes.c_int32
        self.lib.SecKeychainItemModifyAttributesAndData.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p]
        self.lib.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
        self.lib.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.lib.SecKeychainItemDelete.argtypes = [ctypes.c_void_p]
        self.lib.SecKeychainItemDelete.restype = ctypes.c_int32

    def _find(self):
        length, data, item = ctypes.c_uint32(), ctypes.c_void_p(), ctypes.c_void_p()
        status = self.lib.SecKeychainFindGenericPassword(
            None, len(SERVICE), SERVICE, len(ACCOUNT), ACCOUNT,
            ctypes.byref(length), ctypes.byref(data), ctypes.byref(item))
        if status == -25300:
            return None, None
        if status != 0:
            raise CredentialError("macOS Keychain access failed (OSStatus %s). Unlock the login keychain and allow access." % status)
        try:
            value = ctypes.string_at(data, length.value).decode("utf-8")
        finally:
            self.lib.SecKeychainItemFreeContent(None, data)
        return value, item

    def get(self):
        value, item = self._find()
        if item:
            self.cf.CFRelease(item)
        return value

    def set(self, value):
        raw = value.encode("utf-8")
        _, item = self._find()
        if item:
            try:
                status = self.lib.SecKeychainItemModifyAttributesAndData(item, None, len(raw), raw)
            finally:
                self.cf.CFRelease(item)
        else:
            status = self.lib.SecKeychainAddGenericPassword(
                None, len(SERVICE), SERVICE, len(ACCOUNT), ACCOUNT, len(raw), raw, None)
        if status:
            raise CredentialError("macOS Keychain save failed (OSStatus %s)." % status)

    def delete(self):
        _, item = self._find()
        if item:
            try:
                status = self.lib.SecKeychainItemDelete(item)
            finally:
                self.cf.CFRelease(item)
            if status:
                raise CredentialError("macOS Keychain deletion failed (OSStatus %s)." % status)


class WindowsStore:
    def __init__(self):
        from ctypes import wintypes

        class Credential(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR)]

        self.Credential = Credential
        self.lib = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self.lib.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.POINTER(ctypes.POINTER(Credential))]
        self.lib.CredReadW.restype = wintypes.BOOL
        self.lib.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        self.lib.CredWriteW.restype = wintypes.BOOL
        self.lib.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.lib.CredDeleteW.restype = wintypes.BOOL
        self.lib.CredFree.argtypes = [ctypes.c_void_p]

    def get(self):
        ptr = ctypes.POINTER(self.Credential)()
        if not self.lib.CredReadW(WINDOWS_TARGET, 1, 0, ctypes.byref(ptr)):
            if ctypes.get_last_error() == 1168:
                return None
            raise CredentialError("Windows Credential Manager read failed (%s)." % ctypes.get_last_error())
        try:
            return ctypes.string_at(ptr.contents.CredentialBlob,
                                    ptr.contents.CredentialBlobSize).decode("utf-8")
        finally:
            self.lib.CredFree(ptr)

    def set(self, value):
        raw = value.encode("utf-8")
        blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        cred = self.Credential()
        cred.Type, cred.TargetName, cred.UserName = 1, WINDOWS_TARGET, getpass.getuser()
        cred.CredentialBlobSize, cred.CredentialBlob = len(raw), blob
        cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE: per user, not enterprise roaming.
        cred.Comment = "Codex Gemini Bridge - this device only"
        if not self.lib.CredWriteW(ctypes.byref(cred), 0):
            raise CredentialError("Windows Credential Manager save failed (%s)." % ctypes.get_last_error())

    def delete(self):
        if not self.lib.CredDeleteW(WINDOWS_TARGET, 1, 0) and ctypes.get_last_error() != 1168:
            raise CredentialError("Windows Credential Manager deletion failed (%s)." % ctypes.get_last_error())


def store():
    if sys.platform == "darwin":
        return MacStore()
    if sys.platform == "win32":
        return WindowsStore()
    raise CredentialError("Only macOS and Windows are supported; no plaintext credential fallback is provided.")


def validate_key(value):
    value = value.strip()
    if not 20 <= len(value) <= 1024 or any(c.isspace() for c in value) or not value.isascii():
        raise CredentialError("Invalid API key format; paste the Gemini API key without spaces.")
    return value
