"""Unit tests for cluster commands."""

from gcphcp.cli.commands.clusters import _build_cluster_spec, ClusterConfig


def _make_cluster_config(**overrides) -> ClusterConfig:
    """Create a minimal ClusterConfig for testing."""
    defaults = {
        "wif_spec": {"key": "value"},
        "signing_key_base64": "dGVzdA==",
        "issuer_url": "https://issuer.example.com",
        "infra_id": "test-infra",
        "project_id": "test-project",
        "region": "us-central1",
        "network": "test-network",
        "subnet": "test-subnet",
    }
    defaults.update(overrides)
    return ClusterConfig(**defaults)


class TestBuildClusterSpecRelease:
    """Test release fields in _build_cluster_spec."""

    def test_version_only(self):
        """--version without --channel-group uses version in release spec."""
        config = _make_cluster_config()
        result = _build_cluster_spec(
            cluster_name="my-cluster",
            cluster_config=config,
            version="4.22.0",
        )
        assert result["spec"]["release"] == {"version": "4.22.0"}

    def test_version_with_channel_group(self):
        """--version with --channel-group includes both in release spec."""
        config = _make_cluster_config()
        result = _build_cluster_spec(
            cluster_name="my-cluster",
            cluster_config=config,
            version="4.22.0-ec.4",
            channel_group="candidate",
        )
        assert result["spec"]["release"] == {
            "version": "4.22.0-ec.4",
            "channelGroup": "candidate",
        }

    def test_version_with_stable_channel_group(self):
        """Explicit stable channel group is included."""
        config = _make_cluster_config()
        result = _build_cluster_spec(
            cluster_name="my-cluster",
            cluster_config=config,
            version="4.22.0",
            channel_group="stable",
        )
        assert result["spec"]["release"] == {
            "version": "4.22.0",
            "channelGroup": "stable",
        }

    def test_no_version_no_release_key(self):
        """No version means no release key in spec."""
        config = _make_cluster_config()
        result = _build_cluster_spec(
            cluster_name="my-cluster",
            cluster_config=config,
        )
        assert "release" not in result["spec"]

    def test_existing_spec_fields_preserved(self):
        """Release fields don't affect other spec fields."""
        config = _make_cluster_config()
        result = _build_cluster_spec(
            cluster_name="my-cluster",
            cluster_config=config,
            version="4.22.0",
            description="test desc",
        )
        assert result["spec"]["infraID"] == "test-infra"
        assert result["spec"]["platform"]["type"] == "GCP"
        assert result["description"] == "test desc"
        assert result["spec"]["release"]["version"] == "4.22.0"
