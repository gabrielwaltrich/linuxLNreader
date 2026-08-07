from dataclasses import dataclass

import httpx

from novel_reader.errors import DownloadError


@dataclass(slots=True)
class DownloadedPage:
    requested_url: str
    final_url: str
    html: str
    status_code: int


class PageDownloader:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) NovelReader/0.3 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }

    def get(self, url: str) -> DownloadedPage:
        try:
            with httpx.Client(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DownloadError(
                f"O servidor respondeu com HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise DownloadError(f"Não foi possível acessar a página: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower() and not response.text.lstrip().startswith("<"):
            raise DownloadError("A URL não retornou uma página HTML.")

        return DownloadedPage(
            requested_url=url,
            final_url=str(response.url),
            html=response.text,
            status_code=response.status_code,
        )
