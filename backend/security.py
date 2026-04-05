import hashlib
import os
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

def verify_faiss_integrity(index_dir: str) -> bool:
    """
    Calculates SHA-256 hashes of index.faiss and index.pkl in the specified
    directory and verifies them against the expected values in the environment.
    
    If hashes are not configured, it will:
    - ALLOW the load in DEBUG=True mode (with a warning).
    - ABORT the load in DEBUG=False mode (returning False).
    """
    faiss_file = os.path.join(index_dir, "index.faiss")
    pkl_file = os.path.join(index_dir, "index.pkl")

    # 1. Check if both hashes are configured
    if not settings.FAISS_INDEX_HASH or not settings.FAISS_PKL_HASH:
        if settings.DEBUG:
            logger.warning(
                "[SECURITY] FAISS integrity hashes NOT configured in .env. "
                "Allowing load because DEBUG=True, but this is insecure for production!"
            )
            return True
        else:
            logger.error(
                "[SECURITY ALERT] FAISS integrity hashes NOT configured and DEBUG=False. "
                "Aborting FAISS load for safety."
            )
            return False

    # 2. Check if files exist
    if not os.path.exists(faiss_file) or not os.path.exists(pkl_file):
        logger.warning(
            f"[SECURITY] FAISS index files missing in {index_dir}. Cannot verify integrity."
        )
        return False

    # 3. Calculate and verify hashes
    try:
        def get_sha256(filepath):
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                # Read in chunks to handle large index files efficiently
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()

        actual_faiss_hash = get_sha256(faiss_file)
        actual_pkl_hash = get_sha256(pkl_file)

        if (actual_faiss_hash == settings.FAISS_INDEX_HASH and 
            actual_pkl_hash == settings.FAISS_PKL_HASH):
            logger.info(f"[SECURITY] FAISS integrity verified for {index_dir}.")
            return True
        else:
            logger.critical(
                f"[SECURITY ALERT] FAISS index integrity check FAILED for {index_dir}! "
                "The index files may have been tampered with. Aborting deserialization."
            )
            # Detailed mismatch for logs (but potentially sensitive, so we log it as critical)
            logger.critical(f"Expected index.faiss: {settings.FAISS_INDEX_HASH}")
            logger.critical(f"Actual index.faiss:   {actual_faiss_hash}")
            return False

    except Exception as e:
        logger.error(f"[SECURITY] Error during FAISS integrity check: {e}")
        return False
