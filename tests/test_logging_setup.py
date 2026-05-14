import json
import logging
from pathlib import Path
from job_identifier.logging_setup import setup_run_logger


def test_setup_run_logger_writes_json_to_file(tmp_path):
    log_dir = tmp_path / "logs"
    logger, handler = setup_run_logger("run_abc", log_dir=log_dir)
    logger.info("hello", extra={"stage": "test"})
    handler.flush()
    log_file = log_dir / "run_abc.log"
    assert log_file.exists()
    line = log_file.read_text().strip().split("\n")[0]
    parsed = json.loads(line)
    assert parsed["message"] == "hello"
    assert parsed["stage"] == "test"
    logger.removeHandler(handler)
    handler.close()
