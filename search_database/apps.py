from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class SearchAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "search_database"

    nlp_model = None

    def ready(self):
        if self.nlp_model is None:
            self._load_gliner_offline_first()

    def _load_gliner_offline_first(self):
        """
        Load GLiNER model with offline-first approach.

        Strategy:
        1. Check if model exists in HF cache (already downloaded)
        2. If yes, load from cache (no network call)
        3. If no, download from HuggingFace Hub (requires internet)

        Note: HuggingFace uses cache structure:
        - Cache dir: ~/.cache/huggingface/hub/models--<repo>/
        - The repo_id passed to from_pretrained will find it automatically
        """
        import os
        from pathlib import Path
        from gliner import GLiNER

        # Configuration
        repo_id = "urchade/gliner_small-v2.1"

        # Get cache dir (HuggingFace will auto-find it)
        # Priority: 1) HF_HOME env var, 2) default HF cache
        cache_dir = os.getenv("HF_HOME")
        if not cache_dir:
            # Default HuggingFace cache location
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")

        logger.info(f"Cache directory: {cache_dir}")

        # Check if model files exist in cache
        # HuggingFace structure: hub/models--<repo>/snapshots/<commit>/
        model_cache_path = (
            Path(cache_dir) / "hub" / f"models--{repo_id.replace('/', '--')}"
        )

        logger.info(f"Checking for GLiNER model at: {model_cache_path}")

        if model_cache_path.exists():
            # ✅ Model exists in cache - load offline
            logger.info(f"GLiNER model found in cache. Loading from local storage...")
            try:
                # Let HuggingFace find the model in cache
                self.nlp_model = GLiNER.from_pretrained(repo_id)
                logger.info("✅ GLiNER loaded from local cache (offline mode)")
                return
            except Exception as e:
                logger.error(f"Failed to load from cache: {e}")
                logger.info("Attempting to download from HuggingFace Hub...")

        # ❌ Model not in cache - download from hub
        logger.info(
            f"GLiNER model not found in cache. Downloading from HuggingFace Hub..."
        )
        self._download_and_load_from_hub(repo_id)

    def _download_and_load_from_hub(self, repo_id):
        """Download model from HuggingFace Hub and load it."""
        from gliner import GLiNER
        from huggingface_hub import hf_hub_download

        # Determine cache directory
        import os

        cache_dir = os.getenv("HF_HOME") or os.path.join(
            os.path.expanduser("~"), ".cache", "huggingface"
        )

        # Pre-fetch files sequentially (avoid Docker parallel download issues)
        files_to_download = [
            "gliner_config.json",
            "pytorch_model.bin",
            "tokenizer_config.json",
            "tokenizer.json",
            "config.json",
        ]

        logger.info(f"Pre-fetching model files for {repo_id}...")

        for file in files_to_download:
            try:
                logger.info(f"  Fetching {file}...")
                hf_hub_download(
                    repo_id=repo_id,
                    filename=file,
                    cache_dir=cache_dir,
                    resume_download=True,
                )
                logger.info(f"  ✓ {file} fetched")
            except Exception as e:
                logger.warning(f"  ✗ Could not pre-fetch {file}: {e}")

        # Load the model
        logger.info(f"Loading GLiNER model from HuggingFace Hub...")
        try:
            self.nlp_model = GLiNER.from_pretrained(repo_id)
            logger.info("✅ GLiNER downloaded and loaded from HuggingFace Hub")
        except Exception as e:
            logger.error(f"Failed to load GLiNER model: {e}")
            self.nlp_model = None
