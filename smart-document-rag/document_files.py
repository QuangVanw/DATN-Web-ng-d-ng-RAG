from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.oxml.exceptions import InvalidXmlError
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from lxml.etree import XMLSyntaxError
from pypdf import PdfReader
from pypdf.errors import PyPdfError


MAX_TEXT_LENGTH = 1_000_000
MAX_DOCX_UNCOMPRESSED = 60 * 1024 * 1024


def _docx_blocks(container):
    for block in container.iter_inner_content():
        if isinstance(block, Table):
            seen = set()
            for row in block.rows:
                for cell in row.cells:
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        yield from _docx_blocks(cell)
        else:
            yield block.text


def _docx_text(data):
    try:
        with ZipFile(BytesIO(data)) as package:
            entries = package.infolist()
            if (
                len(entries) > 2000
                or sum(entry.file_size for entry in entries) > MAX_DOCX_UNCOMPRESSED
            ):
                raise ValueError("Tệp DOCX có cấu trúc nén quá lớn.")
            if not {"[Content_Types].xml", "_rels/.rels"}.issubset(package.namelist()):
                raise ValueError("Tệp không có cấu trúc DOCX hợp lệ.")
        document = Document(BytesIO(data))
        return _collect_text(_docx_blocks(document), "\n")
    except (BadZipFile, PackageNotFoundError, XMLSyntaxError, InvalidXmlError,
            KeyError, TypeError, OSError, RuntimeError, NotImplementedError) as error:
        raise ValueError("Không đọc được DOCX. Hãy mở và lưu lại tệp bằng Word.") from error


def _collect_text(parts, separator):
    return separator.join(_bounded_parts(parts, separator))


def _bounded_parts(parts, separator):
    result = []
    length = 0
    for part in parts:
        length += len(part) + len(separator)
        if length > MAX_TEXT_LENGTH + len(separator):
            raise ValueError("Văn bản trích xuất vượt quá giới hạn.")
        result.append(part)
    return result


def _pdf_pages(data):
    if not data.startswith(b"%PDF-"):
        raise ValueError("Tệp không có định dạng PDF hợp lệ.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("PDF có mật khẩu không được hỗ trợ.")
        if len(reader.pages) > 200:
            raise ValueError("PDF được phép có tối đa 200 trang.")
        return _bounded_parts((page.extract_text() for page in reader.pages), "\n\n")
    except (PyPdfError, OSError, RecursionError) as error:
        raise ValueError("Không đọc được tệp PDF.") from error


def _txt_text(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Tệp TXT phải dùng mã hóa UTF-8.") from error
    if any(ord(char) < 32 and char not in "\n\r\t\f" for char in text) or text.startswith("%PDF-"):
        raise ValueError("Tệp không phải văn bản TXT hợp lệ.")
    return text


def extract_document(upload, size_limit):
    filename = PurePosixPath(upload.filename.replace(chr(92), "/")).name
    if not filename or len(filename) > 255 or not filename.isprintable():
        raise ValueError("Tên tài liệu không hợp lệ.")
    file_type = PurePosixPath(filename).suffix.lower().lstrip(".")
    readers = {"pdf": _pdf_pages, "docx": _docx_text, "txt": _txt_text}
    if file_type not in readers:
        raise ValueError("Chỉ chấp nhận tài liệu PDF, DOCX hoặc TXT.")

    data = upload.stream.read(size_limit + 1)
    if len(data) > size_limit:
        raise ValueError("Tệp vượt quá giới hạn 10 MB.")

    extracted = readers[file_type](data)
    pages = extracted if file_type == "pdf" else None
    content = ("\n\n".join(pages) if pages is not None else extracted).strip()
    if not content:
        if file_type == "pdf":
            raise ValueError("PDF không có văn bản có thể đọc. Tệp scan cần OCR.")
        raise ValueError("Tài liệu không có văn bản để lưu.")
    if len(content) > MAX_TEXT_LENGTH:
        raise ValueError("Văn bản trích xuất vượt quá giới hạn.")
    return filename, file_type, len(data), content, data, pages
