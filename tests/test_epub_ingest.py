import zipfile

from speaker_split.epub_ingest import extract_raw_blocks, is_meta_text


def _build_min_epub(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version='1.0'?>
<container xmlns='urn:oasis:names:tc:opendocument:xmlns:container' version='1.0'>
  <rootfiles>
    <rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/>
  </rootfiles>
</container>
""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version='1.0' encoding='utf-8'?>
<package xmlns='http://www.idpf.org/2007/opf' version='3.0'>
  <manifest>
    <item id='c1' href='chapter1.xhtml' media-type='application/xhtml+xml'/>
  </manifest>
  <spine>
    <itemref idref='c1'/>
  </spine>
</package>
""",
        )
        zf.writestr(
            "OEBPS/chapter1.xhtml",
            """<html><body>
<h1>目次</h1><h2>第一章</h2><h3>導入</h3>
<p>本文</p><hr/><p>続き</p>
</body></html>""",
        )


def test_extract_h1_h2_h3_p_hr_and_meta(tmp_path):
    epub_path = tmp_path / "sample.epub"
    _build_min_epub(epub_path)

    blocks = extract_raw_blocks(epub_path)
    tags = [b.tag for b in blocks]
    texts = [b.text for b in blocks]

    assert tags == ["h1", "h2", "h3", "p", "hr", "p"]
    assert texts[4] == "---"
    assert blocks[0].is_meta is True
    assert blocks[1].is_meta is False


def test_is_meta_text():
    assert is_meta_text("h1", "目次") is True
    assert is_meta_text("h2", "第一章") is False


def test_extract_raw_blocks_keeps_spine_order_across_documents(tmp_path):
    epub_path = tmp_path / "spine.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version='1.0'?>
<container xmlns='urn:oasis:names:tc:opendocument:xmlns:container' version='1.0'>
  <rootfiles>
    <rootfile full-path='OPS/content.opf' media-type='application/oebps-package+xml'/>
  </rootfiles>
</container>
""",
        )
        zf.writestr(
            "OPS/content.opf",
            """<?xml version='1.0' encoding='utf-8'?>
<package xmlns='http://www.idpf.org/2007/opf' version='3.0'>
  <manifest>
    <item id='a' href='a.xhtml' media-type='application/xhtml+xml'/>
    <item id='b' href='b.xhtml' media-type='application/xhtml+xml'/>
  </manifest>
  <spine>
    <itemref idref='b'/>
    <itemref idref='a'/>
  </spine>
</package>
""",
        )
        zf.writestr("OPS/a.xhtml", "<html><body><p>A</p></body></html>")
        zf.writestr("OPS/b.xhtml", "<html><body><p>B</p></body></html>")

    blocks = extract_raw_blocks(epub_path)
    assert [(b.doc_id, b.text) for b in blocks] == [("OPS/b.xhtml", "B"), ("OPS/a.xhtml", "A")]


def test_is_meta_text_for_url_and_publishing_info_headings():
    assert is_meta_text("h1", "https://example.com") is True
    assert is_meta_text("h2", "2026年4月19日 発行") is True
