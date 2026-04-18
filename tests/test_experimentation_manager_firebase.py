from autora.experiment_runner.experimentation_manager import firebase as firebase_mod


class _FakeDocSnap:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class _FakeDocRef:
    def __init__(self, data):
        self._data = data

    def get(self):
        return _FakeDocSnap(self._data)

    def update(self, patch):
        for key, value in patch.items():
            if "." in key:
                top, sub = key.split(".", 1)
                slot = self._data.setdefault(top, {})
                if not isinstance(slot, dict):
                    slot = {}
                    self._data[top] = slot
                slot[sub] = value
            else:
                self._data[key] = value


class _FakeCollection:
    def __init__(self, data):
        self._data = data

    def document(self, _name):
        return _FakeDocRef(self._data)


class _FakeDb:
    def __init__(self, data):
        self._data = data

    def collection(self, _name):
        return _FakeCollection(self._data)


def _patch_firebase_backend(monkeypatch, meta_data):
    class _FakeCred:
        @staticmethod
        def Certificate(_cred):
            return None

    class _FakeAdmin:
        _apps = []

        @staticmethod
        def initialize_app(_cred):
            _FakeAdmin._apps = [object()]
            return _FakeAdmin._apps[0]

        @staticmethod
        def get_app():
            return _FakeAdmin._apps[0]

        @staticmethod
        def delete_app(_app):
            _FakeAdmin._apps = []

    monkeypatch.setattr(firebase_mod, "firebase_admin", _FakeAdmin)
    monkeypatch.setattr(firebase_mod, "credentials", _FakeCred)
    monkeypatch.setattr(firebase_mod, "firestore", type("F", (), {"client": lambda: _FakeDb(meta_data)}))


def test_check_firebase_status_releases_aborted_pid(monkeypatch):
    meta_data = {"0": {"start_time": 1000, "finished": False, "pId": "pid-1"}}
    _patch_firebase_backend(monkeypatch, meta_data)
    monkeypatch.setattr(firebase_mod.time, "time", lambda: 1005)

    status = firebase_mod.check_firebase_status(
        "autora",
        {"project_id": "demo"},
        time_out=60,
        pids_aborted=["pid-1"],
    )

    assert status == "available"
    assert meta_data["0"]["start_time"] is None
    assert meta_data["0"]["pId"] is None


def test_check_firebase_status_releases_timeout(monkeypatch):
    meta_data = {"0": {"start_time": 1000, "finished": False, "pId": "pid-2"}}
    _patch_firebase_backend(monkeypatch, meta_data)
    monkeypatch.setattr(firebase_mod.time, "time", lambda: 1200)

    status = firebase_mod.check_firebase_status(
        "autora",
        {"project_id": "demo"},
        time_out=60,
        pids_aborted=[],
    )

    assert status == "available"
    assert meta_data["0"]["start_time"] is None


def test_check_firebase_status_release_preserves_extra_meta_fields(monkeypatch):
    """Runner must not wipe client-only keys (e.g. metadata) when freeing a slot."""
    meta_data = {
        "0": {
            "start_time": 1000,
            "finished": False,
            "pId": "pid-1",
            "metadata": True,
        }
    }
    _patch_firebase_backend(monkeypatch, meta_data)
    monkeypatch.setattr(firebase_mod.time, "time", lambda: 1005)

    status = firebase_mod.check_firebase_status(
        "autora",
        {"project_id": "demo"},
        time_out=60,
        pids_aborted=["pid-1"],
    )

    assert status == "available"
    assert meta_data["0"]["start_time"] is None
    assert meta_data["0"]["metadata"] is True
