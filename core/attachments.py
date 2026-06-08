import base64
import mimetypes
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from xml.etree import ElementTree


IMAGE_PART_TYPE = "input_image"
FILE_PART_TYPE = "input_file"
TEXT_PART_TYPE = "text"

DEFAULT_ATTACHMENT_PROMPT = "请查看我上传的附件，并根据需要回答。"
TEXT_EXTENSIONS = {
    ".c",
    ".cpp",
    ".css",
    ".csv",
    ".docx",
    ".html",
    ".java",
    ".js",
    ".json",
    ".log",
    ".md",
    ".pdf",
    ".py",
    ".sql",
    ".text",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_MIME_PREFIXES = ("text/",)
TEXT_MIME_EXACT = {
    "application/javascript",
    "application/json",
    "application/xml",
    "application/x-yaml",
}
SOURCE_UPLOAD = "upload"
SOURCE_CAMERA = "camera"


def sanitize_filename(filename: str) -> str:
    raw_name = Path(filename or "upload").name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._")
    return sanitized or f"upload_{uuid.uuid4().hex[:8]}"


def guess_mime_type(filename: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or fallback


def is_image_mime_type(mime_type: str) -> bool:
    return str(mime_type or "").lower().startswith("image/")


def is_likely_text_file(file_path: Path, mime_type: str) -> bool:
    suffix = file_path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True

    mime_type_lower = str(mime_type or "").lower()
    if any(mime_type_lower.startswith(prefix) for prefix in TEXT_MIME_PREFIXES):
        return True

    return mime_type_lower in TEXT_MIME_EXACT


def attachment_label(part_type: str, source: str = SOURCE_UPLOAD) -> str:
    if part_type == IMAGE_PART_TYPE:
        return "照片" if source == SOURCE_CAMERA else "图片"
    return "文件"


def save_uploaded_files(
    files: Iterable[Any],
    upload_root: str,
    session_id: str,
    source_hint: str = SOURCE_UPLOAD,
) -> List[Dict[str, Any]]:
    upload_root_path = Path(upload_root).resolve()
    upload_dir = upload_root_path / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    attachments: List[Dict[str, Any]] = []
    for storage in files:
        filename = getattr(storage, "filename", "") or ""
        if not filename.strip():
            continue

        safe_name = sanitize_filename(filename)
        stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        target_path = upload_dir / stored_name
        storage.save(target_path)

        mime_type = getattr(storage, "mimetype", "") or guess_mime_type(safe_name)
        attachments.append(
            {
                "name": safe_name,
                "stored_name": stored_name,
                "kind": "image" if is_image_mime_type(mime_type) else "file",
                "mime_type": mime_type,
                "size": target_path.stat().st_size,
                "path": str(target_path),
                "relative_path": str(target_path.relative_to(upload_root_path)).replace(
                    "\\",
                    "/",
                ),
                "source": source_hint or SOURCE_UPLOAD,
            }
        )

    return attachments


def build_user_message_content(prompt: str, attachments: List[Dict[str, Any]]) -> Any:
    prompt_text = prompt.strip()
    if not attachments:
        return prompt_text

    parts: List[Dict[str, Any]] = [
        {
            "type": TEXT_PART_TYPE,
            "text": prompt_text or DEFAULT_ATTACHMENT_PROMPT,
        }
    ]

    for attachment in attachments:
        parts.append(
            {
                "type": (
                    IMAGE_PART_TYPE
                    if attachment.get("kind") == "image"
                    else FILE_PART_TYPE
                ),
                "name": attachment.get("name", "unknown"),
                "path": attachment.get("path", ""),
                "mime_type": attachment.get(
                    "mime_type",
                    "application/octet-stream",
                ),
                "size": int(attachment.get("size", 0)),
                "relative_path": attachment.get("relative_path", ""),
                "source": attachment.get("source", SOURCE_UPLOAD),
            }
        )

    return parts


def describe_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return str(content or "")

    text_parts: List[str] = []
    attachment_lines: List[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")
        if part_type == TEXT_PART_TYPE:
            text = str(part.get("text", "")).strip()
            if text:
                text_parts.append(text)
            continue

        if part_type in {IMAGE_PART_TYPE, FILE_PART_TYPE}:
            source = str(part.get("source", SOURCE_UPLOAD))
            label = attachment_label(part_type, source)
            name = str(part.get("name", "unknown"))
            mime_type = str(part.get("mime_type", "application/octet-stream"))
            size = int(part.get("size", 0))
            attachment_lines.append(f"[{label}] {name} ({mime_type}, {size} bytes)")

    lines = [text for text in text_parts if text]
    lines.extend(attachment_lines)
    return "\n".join(lines).strip()


def build_visible_message(content: Any) -> Dict[str, Any]:
    if isinstance(content, str):
        return {"text": content or "(无文本内容)", "attachments": []}

    if not isinstance(content, list):
        text = str(content or "").strip() or "(无文本内容)"
        return {"text": text, "attachments": []}

    text_parts: List[str] = []
    attachments: List[Dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")
        if part_type == TEXT_PART_TYPE:
            text = str(part.get("text", "")).strip()
            if text:
                text_parts.append(text)
            continue

        if part_type in {IMAGE_PART_TYPE, FILE_PART_TYPE}:
            source = str(part.get("source", SOURCE_UPLOAD))
            attachments.append(
                {
                    "kind": "image" if part_type == IMAGE_PART_TYPE else "file",
                    "kind_label": attachment_label(part_type, source),
                    "name": str(part.get("name", "unknown")),
                    "mime_type": str(
                        part.get("mime_type", "application/octet-stream")
                    ),
                    "size": int(part.get("size", 0)),
                    "relative_path": str(part.get("relative_path", "")),
                    "source": source,
                }
            )

    text = "\n\n".join(text_parts).strip() or "(附件消息)"
    return {"text": text, "attachments": attachments}


def message_contains_images(messages: List[Dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == IMAGE_PART_TYPE:
                return True
    return False


def prepare_messages_for_model(
    messages: List[Dict[str, Any]],
    max_inline_file_bytes: int = 524288,
    max_inline_file_chars: int = 20000,
    allow_image_inputs: bool = True,
) -> List[Dict[str, Any]]:
    prepared_messages: List[Dict[str, Any]] = []
    for message in messages:
        prepared = dict(message)
        if prepared.get("role") == "user" and isinstance(prepared.get("content"), list):
            prepared["content"] = _prepare_user_parts(
                prepared["content"],
                max_inline_file_bytes=max_inline_file_bytes,
                max_inline_file_chars=max_inline_file_chars,
                allow_image_inputs=allow_image_inputs,
            )
        prepared_messages.append(prepared)
    return prepared_messages


def _prepare_user_parts(
    content_parts: List[Dict[str, Any]],
    max_inline_file_bytes: int,
    max_inline_file_chars: int,
    allow_image_inputs: bool,
) -> List[Dict[str, Any]]:
    prepared_parts: List[Dict[str, Any]] = []

    for part in content_parts:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")
        if part_type == TEXT_PART_TYPE:
            text = str(part.get("text", ""))
            if text.strip():
                prepared_parts.append({"type": "text", "text": text})
            continue

        if part_type == IMAGE_PART_TYPE:
            if allow_image_inputs:
                prepared_parts.append(_image_part_to_openai(part))
            else:
                prepared_parts.append(
                    {
                        "type": "text",
                        "text": _image_part_to_text(part),
                    }
                )
            continue

        if part_type == FILE_PART_TYPE:
            prepared_parts.append(
                {
                    "type": "text",
                    "text": _file_part_to_text(
                        part,
                        max_inline_file_bytes=max_inline_file_bytes,
                        max_inline_file_chars=max_inline_file_chars,
                    ),
                }
            )

    if not prepared_parts:
        prepared_parts.append({"type": "text", "text": DEFAULT_ATTACHMENT_PROMPT})
    return prepared_parts


def _image_part_to_openai(part: Dict[str, Any]) -> Dict[str, Any]:
    file_path = Path(str(part.get("path", "")))
    if not file_path.is_file():
        raise FileNotFoundError(f"图片文件不存在：{file_path}")

    mime_type = str(
        part.get("mime_type") or guess_mime_type(file_path.name, "image/png")
    )
    base64_data = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime_type};base64,{base64_data}",
        },
    }


def _image_part_to_text(part: Dict[str, Any]) -> str:
    name = str(part.get("name", "unknown"))
    mime_type = str(part.get("mime_type", "application/octet-stream"))
    size = int(part.get("size", 0))
    return (
        f"用户上传了一张图片《{name}》({mime_type}, {size} bytes)。"
        "但当前模型不支持直接识图，请切换到支持视觉的模型后再分析这张图片。"
    )


def _file_part_to_text(
    part: Dict[str, Any],
    max_inline_file_bytes: int,
    max_inline_file_chars: int,
) -> str:
    file_path = Path(str(part.get("path", "")))
    name = str(part.get("name", file_path.name or "unknown"))
    mime_type = str(part.get("mime_type", guess_mime_type(name)))

    if not file_path.is_file():
        return f"用户上传了文件《{name}》，但当前文件已不存在，无法读取。"

    size = file_path.stat().st_size
    header = f"用户上传了文件《{name}》({mime_type}, {size} bytes)。"

    if size > max_inline_file_bytes:
        return (
            f"{header}\n"
            f"该文件超过当前可内联读取上限 {max_inline_file_bytes} bytes。"
            "请基于文件元信息回答，或提示用户换成更小的文本文件。"
        )

    extracted_text = _extract_supported_file_text(file_path, mime_type)
    if extracted_text is None and is_likely_text_file(file_path, mime_type):
        extracted_text = _read_text_file(file_path)

    if extracted_text is None:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            return (
                f"{header}\n当前环境还不能直接解析 PDF 正文。"
                "请先安装 pypdf，或把 PDF 转成图片/文本后再上传。"
            )
        if suffix == ".doc":
            return (
                f"{header}\n当前仅支持提取 docx 正文，老式 .doc 二进制格式暂不支持自动解析。"
                "建议另存为 .docx 后再上传。"
            )
        return f"{header}\n该文件当前无法自动提取文本内容。"

    truncated = False
    if len(extracted_text) > max_inline_file_chars:
        extracted_text = extracted_text[:max_inline_file_chars]
        truncated = True

    suffix = "\n\n[提示] 文件内容过长，已截断。" if truncated else ""
    return f"{header}\n以下是文件内容：\n\n{extracted_text}{suffix}"


def _extract_supported_file_text(file_path: Path, mime_type: str) -> Optional[str]:
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return _read_docx_file(file_path)
    if suffix == ".pdf":
        return _read_pdf_file(file_path)
    return None


def _read_docx_file(file_path: Path) -> Optional[str]:
    try:
        with zipfile.ZipFile(file_path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except Exception:
        return None

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return None

    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: List[str] = []
    for paragraph in root.findall(".//w:p", namespaces):
        texts = []
        for node in paragraph.findall(".//w:t", namespaces):
            if node.text:
                texts.append(node.text)
        joined = "".join(texts).strip()
        if joined:
            paragraphs.append(joined)

    return "\n".join(paragraphs).strip() or None


def _read_pdf_file(file_path: Path) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except Exception:
        return None

    try:
        reader = PdfReader(str(file_path))
        texts = []
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                texts.append(page_text)
    except Exception:
        return None

    return "\n\n".join(texts).strip() or None


def _read_text_file(file_path: Path) -> Optional[str]:
    raw = file_path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None
