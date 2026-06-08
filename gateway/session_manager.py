import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class SessionManager:
    def __init__(self, history_dir: str) -> None:
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = uuid.uuid4().hex[:8]
        self.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.tool_records: List[Dict[str, Any]] = []
        self.resumed_from_session_id: Optional[str] = None

    def add_tool_record(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        self.tool_records.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    def resume_from_session(self, session_data: Dict[str, Any]) -> None:
        self.resumed_from_session_id = session_data.get("session_id")

    def save_session(
        self,
        model_name: str,
        messages: List[Dict[str, Any]],
    ) -> str:
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = (
            f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.session_id}.json"
        )
        path = self.history_dir / filename

        payload = {
            "session_id": self.session_id,
            "model": model_name,
            "start_time": self.start_time,
            "end_time": end_time,
            "resumed_from_session_id": self.resumed_from_session_id,
            "tool_calls_count": len(self.tool_records),
            "tool_records": self.tool_records,
            "messages": messages,
        }

        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)

    def _iter_session_files(self) -> List[Path]:
        return sorted(self.history_dir.glob("session_*.json"), reverse=True)

    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        for file in self._iter_session_files():
            try:
                return json.loads(file.read_text(encoding="utf-8"))
            except Exception:
                continue
        return None

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id == "latest":
            return self.get_latest_session()

        for file in self._iter_session_files():
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if data.get("session_id") == session_id:
                    return data
            except Exception:
                continue
        return None

    def list_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sessions: List[Dict[str, Any]] = []

        for file in self._iter_session_files():
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                sessions.append(
                    {
                        "session_id": data.get("session_id"),
                        "model": data.get("model"),
                        "start_time": data.get("start_time"),
                        "end_time": data.get("end_time"),
                        "resumed_from_session_id": data.get(
                            "resumed_from_session_id"
                        ),
                        "tool_calls_count": data.get("tool_calls_count", 0),
                        "file": str(file),
                    }
                )
                if limit is not None and len(sessions) >= limit:
                    break
            except Exception:
                continue

        return sessions