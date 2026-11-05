import pytest

from app.store import ProfileStore
from tests.conftest import fake_embedding, load_text


def embed(texts):
    return [fake_embedding(t) for t in texts]


QUERY = "Playwright Python pytest GitHub Actions QA automation croissant sourdough"


def test_tenants_with_same_profile_id_are_isolated(store, cv_text):
    other = load_text("cv_other_tenant.txt")
    store.index_profile("tenant-a", "cv-1", cv_text, embed)
    store.index_profile("tenant-b", "cv-1", other, embed)

    a = store.retrieve("tenant-a", "cv-1", QUERY, embed, top_k=10)
    b = store.retrieve("tenant-b", "cv-1", QUERY, embed, top_k=10)

    assert a and b
    assert not any("croissant" in e["excerpt"] for e in a)
    assert not any("Playwright" in e["excerpt"] for e in b)


def test_other_tenant_cannot_read_profile(store, cv_text):
    store.index_profile("tenant-a", "cv-1", cv_text, embed)
    assert store.retrieve("tenant-b", "cv-1", QUERY, embed, top_k=5) == []


def test_tenant_metadata_filter_drops_foreign_chunks(store, chroma_client, cv_text):
    # Simulate a corrupted/shared collection: a chunk tagged with another tenant must not leak.
    store.index_profile("tenant-a", "cv-1", cv_text, embed)
    col = chroma_client.get_collection(ProfileStore._collection_name("tenant-a", "cv-1"))
    col.add(ids=["foreign"], documents=["Playwright secret of tenant B"],
            embeddings=embed(["Playwright secret of tenant B"]),
            metadatas=[{"source_id": "CV-X", "tenant_id": "tenant-b"}])
    results = store.retrieve("tenant-a", "cv-1", "Playwright", embed, top_k=10)
    assert all("tenant B" not in e["excerpt"] for e in results)


@pytest.mark.parametrize("tenant,profile", [("user-123@example.com", "cv-1"), ("tenant-a", "profile-xyz")])
def test_collection_name_hides_identifiers(tenant, profile):
    name = ProfileStore._collection_name(tenant, profile)
    assert tenant not in name and profile not in name
    assert name.startswith("profile_") and len(name) == len("profile_") + 32


def test_collection_name_is_unambiguous():
    assert ProfileStore._collection_name("a", "b") != ProfileStore._collection_name("b", "a")


def test_reindex_replaces_old_chunks(store, cv_text):
    store.index_profile("tenant-a", "cv-1", cv_text, embed)
    store.index_profile("tenant-a", "cv-1", "Pastry chef with croissant experience.", embed)
    results = store.retrieve("tenant-a", "cv-1", QUERY, embed, top_k=10)
    assert len(results) == 1
    assert "Playwright" not in results[0]["excerpt"]


def test_unknown_profile_returns_empty(store):
    assert store.retrieve("tenant-a", "never-indexed", QUERY, embed, top_k=5) == []


def test_top_k_larger_than_chunk_count(store, cv_text):
    n = store.index_profile("tenant-a", "cv-1", cv_text, embed)
    results = store.retrieve("tenant-a", "cv-1", QUERY, embed, top_k=50)
    assert len(results) == n


def test_source_ids_are_sequential(store, cv_text):
    n = store.index_profile("tenant-a", "cv-1", cv_text, embed)
    results = store.retrieve("tenant-a", "cv-1", QUERY, embed, top_k=n)
    assert sorted(e["source_id"] for e in results) == [f"CV-{i}" for i in range(1, n + 1)]
    assert all(isinstance(e["relevance_distance"], float) for e in results)


def test_empty_profile_rejected(store):
    with pytest.raises(ValueError):
        store.index_profile("tenant-a", "cv-1", "  \n ", embed)
