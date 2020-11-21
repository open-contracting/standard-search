from urllib.parse import urljoin

import lxml.html
import requests
from lxml import etree


def extract_section(section):
    all_text = []

    for part in section.xpath("node()"):
        if isinstance(part, str):
            text = str(part)
        else:
            if "section" in part.get("class", ""):
                continue
            text = part.text_content()

        lines = (line.strip().rstrip("¶") for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(filter(None, chunks))
        all_text.append(text)

    return "\n".join(all_text), section.attrib["id"]


def extract_page(local_url, remote_url):
    response = requests.get(local_url)
    response.raise_for_status()
    response.encoding = "utf-8"

    document = lxml.html.fromstring(response.content)

    for element in ("script", "style"):
        etree.strip_elements(document, element)

    page_results = []
    for section in document.xpath("//div[contains(@class, 'section')]"):
        if "expandjson" in section.attrib["class"]:
            continue

        text, section_id = extract_section(section)

        title = document.xpath("//title/text()")[0].split("—")[0].strip()
        section_title = section.xpath("h1|h2|h3|h4|h5")[0].text_content().rstrip("¶")

        if title != section_title:
            title = f"{title} - {section_title}"

        page_results.append(
            {
                "url": f"{remote_url}#{section_id}",
                "text": text,
                "title": title,
            }
        )

    href = document.xpath("//a[@accesskey='n']/@href")
    if href:
        href = href[0]

    return page_results, href


def process(url, remote_url):
    results = []
    local_url = href = url

    while href:
        page_results, href = extract_page(local_url, remote_url)
        local_url = urljoin(local_url, href)
        remote_url = urljoin(remote_url, href)
        results.extend(page_results)

    return results
