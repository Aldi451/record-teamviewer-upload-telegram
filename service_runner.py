import os
import time
import logging
import servicemanager
import win32event
import win32service
import win32serviceutil

from upload_telegram import run_automation, init_db, setup_logging


class TelegramUploadService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PowerProTelegramUploader"
    _svc_display_name_ = "PowerPro Telegram Uploader"
    _svc_description_ = "Mengarsip dan upload file .tvs ke Telegram tanpa prompt dan tanpa jendela console."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main_loop()

    def main_loop(self):
        setup_logging()
        init_db()
        logging.info("Windows service started.")

        while True:
            try:
                run_automation()
            except Exception as exc:
                logging.exception(f"Service error: {exc}")

            wait_result = win32event.WaitForSingleObject(self.stop_event, 300000)
            if wait_result == win32event.WAIT_OBJECT_0:
                break

        logging.info("Windows service stopped.")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TelegramUploadService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(TelegramUploadService)
