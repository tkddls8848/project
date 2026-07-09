"""faiss 인덱스 I/O 헬퍼.

Windows에서 faiss(C++ FileIOReader/Writer)는 narrow `fopen`을 사용하므로, 경로에
비ASCII(예: 한글) 문자가 있으면 현재 코드페이지로 인코딩되지 못해
`Illegal byte sequence`(EILSEQ)로 열기에 실패한다. 이 프로젝트의 디렉터리명
`nara_search(API문서검색)`가 그 경우다.

경로가 ASCII가 아니면 ASCII 임시 파일을 경유해 읽고 쓴다. 파이썬의 파일 연산은
유니코드 경로를 정상 처리하므로 임시 파일과 최종 경로 사이 이동/복사는 문제없다.
"""
import os
import shutil
import tempfile


def _is_ascii(s: str) -> bool:
    return all(ord(c) < 128 for c in s)


def write_index(index, dest) -> None:
    """faiss.write_index. 비ASCII 경로면 ASCII 임시파일에 쓴 뒤 최종 위치로 이동."""
    import faiss

    dest = str(dest)
    if _is_ascii(dest):
        faiss.write_index(index, dest)
        return

    fd, tmp = tempfile.mkstemp(suffix=".index")
    os.close(fd)
    try:
        faiss.write_index(index, tmp)
        if os.path.exists(dest):
            os.remove(dest)
        shutil.move(tmp, dest)   # 같은 드라이브면 rename, 아니면 copy+delete
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_index(src):
    """faiss.read_index. 비ASCII 경로면 ASCII 임시파일로 복사해 읽는다."""
    import faiss

    src = str(src)
    if _is_ascii(src):
        return faiss.read_index(src)

    fd, tmp = tempfile.mkstemp(suffix=".index")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        return faiss.read_index(tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
