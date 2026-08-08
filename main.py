from novel_reader.logging_setup import configure_logging, get_logger
from novel_reader.error_handling import log_exception, write_crash_report
from novel_reader.app import run

if __name__ == "__main__":
    configure_logging(debug=False)
    raise SystemExit(run())
