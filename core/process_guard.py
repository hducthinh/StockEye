import os
import sys
import atexit
import ctypes
from ctypes import wintypes

_global_job_handle = None
_registered_pids = set()

def setup_windows_job_object():
    """
    Gán tiến trình hiện tại vào Windows Job Object với cờ JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
    Bất kỳ tiến trình con nào (kể cả chrome.exe / Stockfish) khi cha bị tắt
    (bấm nút X, tắt terminal, bị kill từ Task Manager hoặc crash)
    sẽ được Kernel Windows tự động tiêu diệt 100%, không bao giờ bị chạy ngầm.
    """
    global _global_job_handle
    if sys.platform != "win32":
        return None

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

        hJob = kernel32.CreateJobObjectW(None, None)
        if not hJob:
            return None

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoCounters", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryLimit", ctypes.c_size_t),
                ("PeakJobMemoryLimit", ctypes.c_size_t),
            ]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JobObjectExtendedLimitInformation = 9

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        set_ok = kernel32.SetInformationJobObject(
            hJob,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info)
        )

        assign_ok = kernel32.AssignProcessToJobObject(hJob, kernel32.GetCurrentProcess())
        if assign_ok:
            _global_job_handle = hJob
            return hJob
    except Exception as e:
        print(f"[ProcessGuard] Cảnh báo cấu hình Job Object: {e}")
    return None


def cleanup_zombie_engines(engine_dir=None):
    """
    Quét và tiêu diệt các tiến trình chrome.exe hoặc stockfish cũ bị sót lại từ phiên trước.
    LƯU Ý QUAN TRỌNG: Chỉ tiêu diệt tiến trình có đường dẫn xuất phát từ thư mục engine của StockEye,
    tuyệt đối KHÔNG đụng đến trình duyệt Google Chrome thật của người dùng.
    """
    if engine_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        engine_dir = os.path.join(base_dir, "engine")
    
    engine_dir_clean = os.path.abspath(engine_dir).lower()
    
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                exe = (p.info.get('exe') or '').lower()
                # Chỉ xử lý nếu file thực thi nằm trong thư mục engine của project
                if exe and engine_dir_clean in exe:
                    print(f"[ProcessGuard] Phát hiện tiến trình engine cũ còn chạy ngầm: PID {p.pid} ({exe}). Đang dọn dẹp...")
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        # Fallback nếu psutil chưa cài đặt
        pass


def kill_pid_force(pid):
    """Tiêu diệt tức thì tiến trình theo PID qua Windows API"""
    if not pid:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_TERMINATE = 0x0001
        hProcess = kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
        if hProcess:
            kernel32.TerminateProcess(hProcess, 1)
            kernel32.CloseHandle(hProcess)
    except Exception:
        try:
            os.kill(int(pid), 9)
        except Exception:
            pass


def register_engine_pid(pid):
    """Đăng ký PID của engine để đảm bảo luôn bị dọn dẹp khi app thoát"""
    if pid:
        _registered_pids.add(pid)


def unregister_engine_pid(pid):
    if pid in _registered_pids:
        _registered_pids.remove(pid)


def _atexit_cleanup():
    """Tự động gọi khi Python thoát"""
    for pid in list(_registered_pids):
        kill_pid_force(pid)
    _registered_pids.clear()

atexit.register(_atexit_cleanup)


def init_process_guard():
    """Khởi tạo toàn diện cơ chế bảo vệ tiến trình"""
    # 1. Dọn sạch tiến trình thừa cũ nếu có
    cleanup_zombie_engines()
    # 2. Cài đặt Windows Job Object để tự diệt khi tắt
    setup_windows_job_object()
