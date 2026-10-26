"""Frozen, local English sentence embeddings; no student text leaves the machine."""

import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

import numpy as np

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
FILES = ("onnx/model.onnx", "tokenizer.json")
ASSET_SHA256 = {
    'onnx/model.onnx': '6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452',
    'tokenizer.json': 'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037',
}


def digest_texts(texts):
    return hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode("utf-8")).hexdigest()


def mean_pool(tokens, mask):
    """Attention-mask mean pooling followed by L2 normalization (model-card recipe)."""
    weights = np.asarray(mask, dtype=np.float32)[..., None]
    pooled = (tokens * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1e-9)
    return pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)


def prepare_model(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        target = directory / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            print(f"Downloading public model asset: {filename}", flush=True)
            temporary = target.with_suffix(target.suffix + ".partial")
            url = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{filename}"
            with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            temporary.replace(target)
    hashes = {filename: hashlib.sha256((directory / filename).read_bytes()).hexdigest() for filename in FILES}
    if hashes != ASSET_SHA256:
        raise ValueError('Public model asset checksum mismatch; replace modified assets from the pinned revision')
    return hashes


def encode_local(texts, directory, batch_size=32):
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise ValueError("Semantic retrieval requires the optional embeddings dependencies: pip install -e '.[embeddings]'") from exc
    hashes = prepare_model(directory)
    tokenizer = Tokenizer.from_file(str(Path(directory) / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=256)
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(Path(directory) / "onnx/model.onnx"), options,
                                  providers=["CPUExecutionProvider"])
    vectors, truncated = [], 0
    # Count truncation with the same tokenizer, before enabling the 256-token limit.
    tokenizer.no_truncation()
    for start in range(0, len(texts), batch_size):
        truncated += sum(len(item.ids) > 256 for item in tokenizer.encode_batch(texts[start:start + batch_size]))
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
    for start in range(0, len(texts), batch_size):
        encoded = tokenizer.encode_batch(texts[start:start + batch_size])
        feeds = {"input_ids": np.array([x.ids for x in encoded], dtype=np.int64),
                 "attention_mask": np.array([x.attention_mask for x in encoded], dtype=np.int64),
                 "token_type_ids": np.array([x.type_ids for x in encoded], dtype=np.int64)}
        feeds = {x.name: feeds[x.name] for x in session.get_inputs()}
        tokens = session.run(None, feeds)[0]
        if tokens.ndim != 3 or tokens.shape[-1] != 384:
            raise ValueError("Unexpected ONNX output; expected batch/token/384 hidden states")
        vectors.append(mean_pool(tokens, feeds["attention_mask"]))
        if start % (batch_size * 100) == 0:
            print(f"Encoded {min(start + batch_size, len(texts))}/{len(texts)} responses locally", flush=True)
    return np.concatenate(vectors), {"model": MODEL, "revision": REVISION, "asset_sha256": hashes,
                                      "dimensions": 384, "max_tokens": 256, "truncated_rows": truncated,
                                      "pooling": "attention-mask mean + L2", "input": "caller-supplied texts, independently encoded"}


def cached_embeddings(texts, model_dir, cache_path):
    """Cache is bound to ordered inputs, fixed model revision and pooling recipe."""
    cache_path = Path(cache_path)
    if cache_path.suffix != '.npz':
        raise ValueError('Embedding cache path must end with .npz')
    identity = {"text_sha256": digest_texts(texts), "revision": REVISION, "recipe": "explanation-mean-l2-256-v1"}
    persist_metadata = False
    if cache_path.exists():
        with np.load(cache_path, allow_pickle=False) as cache:
            metadata = json.loads(str(cache["metadata"]))
            vectors = cache["vectors"]
        if metadata["identity"] != identity:
            raise ValueError("Embedding cache does not match ordered inputs/model recipe; use a new cache path")
    else:
        vectors, encoding = encode_local(texts, model_dir)
        metadata = {"identity": identity, "encoding": encoding}
        persist_metadata = True
    if vectors.shape != (len(texts), 384) or not np.isfinite(vectors).all():
        raise ValueError("Invalid embedding cache shape or nonfinite values")
    vector_hash = hashlib.sha256(vectors.tobytes()).hexdigest()
    if metadata.get('vectors_sha256', vector_hash) != vector_hash:
        raise ValueError('Embedding cache vector checksum mismatch')
    # Upgrade older local caches once, retaining their text/model identity.
    persist_metadata |= 'vectors_sha256' not in metadata
    metadata['vectors_sha256'] = vector_hash
    metadata['encoding']['input'] = 'caller-supplied texts, independently encoded'
    if persist_metadata:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache_path, vectors=vectors, metadata=json.dumps(metadata, sort_keys=True))
    return vectors, metadata
