#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
네이버 미디어 랭킹 페이지 크롤러
https://media.naver.com/press/001/ranking?type=popular 페이지에서
li.as_thumb 요소의 a 태그 href 링크를 수집하고, 기사 본문을 추출합니다.

사용법:
  python naver_media_crawler.py                    # 링크 수집 + 본문 추출
  python naver_media_crawler.py --enrich-only FILE # 기존 JSON 파일의 본문만 추출
"""
import requests
from bs4 import BeautifulSoup
import json
import re
import argparse
from datetime import datetime


def crawl_naver_media_ranking(url="https://media.naver.com/press/001/ranking?type=popular"):
    """
    네이버 미디어 랭킹 페이지에서 기사 링크를 크롤링합니다.

    Args:
        url: 크롤링할 페이지 URL

    Returns:
        링크 리스트
    """
    try:
        # 페이지 요청
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        print(f"페이지 요청 중: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')

        # li.as_thumb 요소 찾기
        li_elements = soup.find_all('li', class_='as_thumb')

        print(f"\n찾은 li.as_thumb 요소 개수: {len(li_elements)}")

        # 링크 추출
        links = []
        for idx, li in enumerate(li_elements, 1):
            # li 태그 내의 a 태그 찾기
            a_tag = li.find('a')
            if a_tag and a_tag.get('href'):
                href = a_tag['href']

                # 상대 경로인 경우 절대 경로로 변환
                if href.startswith('/'):
                    href = 'https://media.naver.com' + href

                # 추가 정보 수집 (제목 등)
                raw_text = a_tag.get('title', '') or a_tag.get_text(strip=True)

                # 텍스트 파싱: "1제목조회수18,739" 형식에서 제목과 조회수 분리
                # 맨 앞 숫자(인덱스) 제거
                text_without_index = re.sub(r'^\d+', '', raw_text)

                # 조회수 추출
                count = None
                count_match = re.search(r'조회수([\d,]+)', text_without_index)
                if count_match:
                    count_str = count_match.group(1).replace(',', '')
                    count = int(count_str)
                    # 조회수 부분 제거하여 제목만 남김
                    title = re.sub(r'조회수[\d,]+', '', text_without_index).strip()
                else:
                    title = text_without_index.strip()

                link_data = {
                    'index': idx,
                    'url': href,
                    'title': title,
                    'count': count
                }

                links.append(link_data)
                count_display = f"{count:,}" if count else "N/A"
                print(f"[{idx}] {title[:50]}... (조회수: {count_display})")

        return links

    except requests.exceptions.RequestException as e:
        print(f"페이지 요청 실패: {e}")
        return []
    except Exception as e:
        print(f"크롤링 중 오류 발생: {e}")
        return []


def fetch_article_content(url):
    """
    뉴스 기사 URL에서 article 태그의 텍스트를 추출합니다.

    Args:
        url: 뉴스 기사 URL

    Returns:
        article 태그의 텍스트 (문자열)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # article 태그 찾기
        article = soup.find('article')

        if not article:
            return ""

        # 이미지, 자료화면 등을 나타내는 요소 제거
        # span 태그 중 특정 클래스를 가진 것들 제거
        for element in article.find_all(['span'], class_=lambda x: x and ('image' in x.lower() or 'photo' in x.lower() or 'caption' in x.lower())):
            element.decompose()

        # script, style 태그 제거
        for element in article.find_all(['script', 'style']):
            element.decompose()

        # 텍스트 추출
        text = article.get_text(separator='\n', strip=True)

        # 연속된 줄바꿈 정리
        text = re.sub(r'\n\s*\n', '\n\n', text)

        # 기자 이메일 주소 제거 (맨 마지막 줄의 이메일)
        # 일반적인 이메일 패턴: xxx@yyy.zzz
        text = re.sub(r'\n?[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*$', '', text)

        return text.strip()

    except Exception as e:
        print(f"  - 기사 본문 추출 실패: {e}")
        return ""


def enrich_articles_from_json(json_file):
    """
    JSON 파일을 읽어서 각 링크의 기사 본문을 추출하고 저장합니다.

    Args:
        json_file: JSON 파일 경로
    """
    try:
        # JSON 파일 읽기
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        links = data.get('links', [])

        print(f"\n총 {len(links)}개의 기사 본문을 추출합니다...")
        print("=" * 70)

        # 각 링크의 기사 본문 추출
        for idx, link in enumerate(links, 1):
            url = link.get('url')
            title = link.get('title', '')

            print(f"\n[{idx}/{len(links)}] {title[:50]}...")
            print(f"  URL: {url}")

            # 기사 본문 추출
            article_content = fetch_article_content(url)

            if article_content:
                link['article'] = article_content
                print(f"  - 본문 추출 완료 (길이: {len(article_content)} 자)")
            else:
                link['article'] = ""
                print(f"  - 본문 추출 실패")

        # 수정된 데이터를 다시 저장
        data['enriched_at'] = datetime.now().isoformat()

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 70)
        print(f"기사 본문이 '{json_file}' 파일에 추가되었습니다.")

    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {json_file}")
    except Exception as e:
        print(f"오류 발생: {e}")


def _parse_metadata(output: str):
    """LLM 출력에서 topic, summary, keywords 파싱"""
    topic = ""
    summary = ""
    keywords = []

    for line in output.split('\n'):
        line = line.strip()
        if line.lower().startswith('topic:'):
            topic = line.split(':', 1)[1].strip()
        elif line.lower().startswith('summary:'):
            summary = line.split(':', 1)[1].strip()
        elif line.lower().startswith('keywords:'):
            kw_str = line.split(':', 1)[1].strip()
            keywords = [k.strip() for k in kw_str.split(',') if k.strip()][:5]

    return topic, summary, keywords


def generate_article_metadata(json_file, ollama_url="http://localhost:11434"):
    """
    기사에 LLM 기반 topic, summary, keywords를 생성하여 저장.

    Args:
        json_file: media_links JSON 파일 경로
        ollama_url: Ollama 서버 URL
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        links = data.get('links', [])
        print(f"\n총 {len(links)}개 기사의 메타데이터를 생성합니다...")
        print("=" * 70)

        for idx, link in enumerate(links, 1):
            title = link.get('title', '')
            article = link.get('article', '')

            print(f"\n[{idx}/{len(links)}] {title[:50]}...")

            if not article:
                print(f"  SKIP - 본문 없음")
                continue

            if link.get('keywords'):
                print(f"  SKIP - 이미 keywords 존재: {link['keywords']}")
                continue

            prompt = (
                "다음 신문기사를 분석하여 아래 형식으로만 응답하세요. 다른 텍스트는 작성하지 마세요.\n\n"
                f"기사:\n{article[:1500]}\n\n"
                "응답 형식:\n"
                "topic: (기사의 핵심 주제를 한 줄로)\n"
                "summary: (기사를 2~3문장으로 요약)\n"
                "keywords: 키워드1,키워드2,키워드3,키워드4,키워드5"
            )

            try:
                response = requests.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": "gemma3:4b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9,
                            "num_predict": 200
                        }
                    },
                    timeout=30
                )
                response.raise_for_status()

                output = response.json().get('response', '')
                print(f"  LLM raw: {output[:100]}...")

                topic, summary, keywords = _parse_metadata(output)

                if keywords:
                    link['topic'] = topic
                    link['summary'] = summary
                    link['keywords'] = keywords
                    print(f"  OK - keywords: {keywords}")
                else:
                    print(f"  WARN - keywords 파싱 실패")

            except Exception as e:
                print(f"  ERROR: {e}")

        # 저장
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 70)
        print(f"메타데이터가 '{json_file}' 파일에 저장되었습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")


def save_to_json(links, filename=None):
    """
    링크 데이터를 JSON 파일로 저장합니다.

    Args:
        links: 링크 리스트
        filename: 저장할 파일명 (기본값: media_links_YYYYMMDD.json)
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"media_links_{timestamp}.json"

    data = {
        'crawled_at': datetime.now().isoformat(),
        'total_count': len(links),
        'links': links
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n결과가 '{filename}' 파일로 저장되었습니다.")
    return filename


def main():
    """메인 함수"""
    # 커맨드라인 인자 파싱
    parser = argparse.ArgumentParser(
        description='네이버 미디어 랭킹 크롤러',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python naver_media_crawler.py                         # 링크 수집 + 본문 추출 + keywords 생성
  python naver_media_crawler.py --enrich-only FILE.json # 기존 JSON의 본문만 추출
  python naver_media_crawler.py --keywords-only FILE.json # 기존 JSON에 keywords만 생성
        """
    )
    parser.add_argument(
        '--enrich-only',
        type=str,
        metavar='FILE',
        help='크롤링 없이 기존 JSON 파일의 기사 본문만 추출'
    )
    parser.add_argument(
        '--keywords-only',
        type=str,
        metavar='FILE',
        help='기존 JSON 파일에 LLM 기반 keywords/topic/summary만 생성'
    )
    parser.add_argument(
        '--url',
        type=str,
        default="https://media.naver.com/press/001/ranking?type=popular",
        help='크롤링할 페이지 URL (기본값: 연합뉴스 인기기사)'
    )

    args = parser.parse_args()

    # --keywords-only 모드: 기존 JSON 파일에 keywords만 생성
    if args.keywords_only:
        print("=" * 70)
        print("기사 메타데이터 생성 (keywords/topic/summary)")
        print("=" * 70)
        print(f"대상 파일: {args.keywords_only}")
        generate_article_metadata(args.keywords_only)
        print("\n완료!")
        return

    # --enrich-only 모드: 기존 JSON 파일의 본문만 추출
    if args.enrich_only:
        print("=" * 70)
        print("네이버 뉴스 기사 본문 추출 (기존 파일)")
        print("=" * 70)
        print(f"대상 파일: {args.enrich_only}")
        enrich_articles_from_json(args.enrich_only)
        print("\n완료!")
        return

    # 일반 크롤링 모드
    print("=" * 70)
    print("네이버 미디어 랭킹 크롤러")
    print("=" * 70)

    # 크롤링 실행
    links = crawl_naver_media_ranking(args.url)

    if not links:
        print("\n크롤링 결과가 없습니다.")
        return

    print("\n" + "=" * 70)
    print(f"총 {len(links)}개의 링크를 수집했습니다.")
    print("=" * 70)

    # JSON 파일로 저장
    json_file = save_to_json(links)

    # 기사 본문 추출 (기본 동작)
    print("\n" + "=" * 70)
    print("기사 본문 추출 시작")
    print("=" * 70)
    enrich_articles_from_json(json_file)

    # 메타데이터 생성 (keywords, topic, summary)
    print("\n" + "=" * 70)
    print("기사 메타데이터 생성 시작")
    print("=" * 70)
    generate_article_metadata(json_file)

    # 요약 출력
    print("\n[수집된 링크 목록]")
    for link in links[:5]:  # 처음 5개만 출력
        print(f"  - {link['title'][:60]}")

    if len(links) > 5:
        print(f"  ... 외 {len(links) - 5}개")

    print("\n완료!")


if __name__ == "__main__":
    main()
