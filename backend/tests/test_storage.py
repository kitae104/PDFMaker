from app.services.storage import StorageService, sanitize_filename


def test_sanitize_filename_removes_path():
    assert sanitize_filename("../bad file.mp4") == "bad_file.mp4"


def test_storage_job_dir(tmp_path):
    service = StorageService(tmp_path)
    path = service.job_dir("a" * 32)
    assert (path / "source").exists()
    assert (path / "pdf").exists()
