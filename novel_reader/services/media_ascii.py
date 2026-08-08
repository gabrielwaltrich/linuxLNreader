from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps


ASCII_RAMP = "@%#*+=-:. "


class MediaAsciiError(RuntimeError):
    pass


@dataclass(slots=True)
class AsciiRenderResult:
    text: str
    backend: str
    source_path: Path


class ChafaBackend:
    name = "chafa"

    @staticmethod
    def available() -> bool:
        return shutil.which("chafa") is not None

    def render(
        self,
        path: str | Path,
        *,
        width: int = 34,
        height: int = 18,
    ) -> str:
        executable = shutil.which("chafa")
        if not executable:
            raise MediaAsciiError("Chafa não está instalado.")

        command = [
            executable,
            "-f", "symbols",
            "-c", "none",
            "--animate", "off",
            "--probe", "off",
            "-s", f"{max(4, int(width))}x{max(2, int(height))}",
            "--symbols", "ascii",
            str(path),
        ]

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise MediaAsciiError(f"Falha ao executar Chafa: {exc}") from exc

        if process.returncode != 0 or not process.stdout.strip():
            message = process.stderr.strip() or "Chafa não produziu saída."
            raise MediaAsciiError(message)

        return process.stdout.rstrip()


class PillowAsciiBackend:
    name = "pillow"

    def render(
        self,
        path: str | Path,
        *,
        width: int = 34,
        height: int = 18,
    ) -> str:
        width = max(4, int(width))
        height = max(2, int(height))

        try:
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original).convert("L")

                # Caracteres de terminal tendem a ser aproximadamente duas
                # vezes mais altos do que largos. Compensamos antes do fit.
                image = ImageOps.contain(
                    image,
                    (width, max(1, height * 2)),
                    method=Image.Resampling.LANCZOS,
                )

                target_height = min(height, max(1, image.height // 2))
                image = image.resize(
                    (min(width, image.width), target_height),
                    Image.Resampling.LANCZOS,
                )

                get_flat = getattr(image, "get_flattened_data", None)
                pixels = list(get_flat() if get_flat else image.getdata())
        except Exception as exc:
            raise MediaAsciiError(f"Não foi possível abrir a imagem: {exc}") from exc

        rows: list[str] = []
        image_width = image.width
        for y in range(image.height):
            chars = []
            for x in range(image_width):
                value = pixels[y * image_width + x]
                index = round((value / 255) * (len(ASCII_RAMP) - 1))
                chars.append(ASCII_RAMP[index])
            rows.append("".join(chars).rstrip())

        return "\n".join(rows).rstrip()


class MediaAsciiService:
    """Baixa/cacheia mídia e converte imagens estáticas para texto ASCII.

    Chafa é preferido quando instalado. O fallback Pillow mantém o recurso
    funcional em instalações Python sem Chafa.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        client: httpx.Client | None = None,
    ):
        if cache_dir is None:
            try:
                from PySide6.QtCore import QStandardPaths

                base = Path(
                    QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.CacheLocation
                    )
                )
            except Exception:
                base = Path.home() / ".cache" / "novel-reader"
            cache_dir = base / "ascii-media"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = client

    @property
    def backend_name(self) -> str:
        return "chafa" if ChafaBackend.available() else "pillow"

    def render_url(
        self,
        url: str,
        *,
        width: int = 34,
        height: int = 18,
        force_refresh: bool = False,
    ) -> AsciiRenderResult:
        if not url:
            raise MediaAsciiError("A obra não possui URL de capa.")

        path = self.fetch(url, force_refresh=force_refresh)
        return self.render_path(path, width=width, height=height)

    def render_path(
        self,
        path: str | Path,
        *,
        width: int = 34,
        height: int = 18,
    ) -> AsciiRenderResult:
        path = Path(path)
        if not path.exists():
            raise MediaAsciiError(f"Imagem não encontrada: {path}")

        if ChafaBackend.available():
            try:
                text = ChafaBackend().render(path, width=width, height=height)
                return AsciiRenderResult(text=text, backend="chafa", source_path=path)
            except MediaAsciiError:
                # A presença do executável não garante suporte ao codec da
                # imagem. Pillow continua sendo um fallback útil.
                pass

        text = PillowAsciiBackend().render(path, width=width, height=height)
        return AsciiRenderResult(text=text, backend="pillow", source_path=path)

    def fetch(self, url: str, *, force_refresh: bool = False) -> Path:
        path = self._cache_path(url)
        if path.exists() and path.stat().st_size > 0 and not force_refresh:
            return path

        client = self._client
        close_client = client is None
        if client is None:
            client = httpx.Client(
                follow_redirects=True,
                timeout=20,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 NovelReader/0.5.1"
                    )
                },
            )

        try:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").casefold()
            if content_type and not (
                content_type.startswith("image/")
                or "octet-stream" in content_type
            ):
                raise MediaAsciiError(
                    f"A URL da capa retornou conteúdo inesperado: {content_type}"
                )
            path.write_bytes(response.content)
        except MediaAsciiError:
            raise
        except Exception as exc:
            raise MediaAsciiError(f"Falha ao baixar capa: {exc}") from exc
        finally:
            if close_client:
                client.close()

        if not path.exists() or path.stat().st_size == 0:
            raise MediaAsciiError("A capa baixada está vazia.")

        return path

    def _cache_path(self, url: str) -> Path:
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            suffix = ".img"

        digest = sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}{suffix}"
