"""Unit tests for hypershift utilities."""

import os
import pytest
from unittest.mock import patch, MagicMock
import subprocess

from gcphcp.utils.hypershift import (
    HypershiftError,
    get_hypershift_binary,
    require_hypershift_binary,
    check_hypershift_installed,
    validate_iam_config,
    validate_infra_config,
    validate_infra_id,
    validate_infra_id_length,
    iam_config_to_wif_spec,
    destroy_iam_gcp,
    destroy_infra_gcp,
    SERVICE_ACCOUNTS,
    MAX_INFRA_ID_LENGTH,
    INFRA_ID_PATTERN,
)


class TestGetHypershiftBinary:
    """Tests for get_hypershift_binary function."""

    def test_get_hypershift_binary_from_env(self, tmp_path):
        """When HYPERSHIFT_BINARY env is set it should return that path."""
        binary_path = tmp_path / "hypershift"
        binary_path.touch()

        with patch.dict(os.environ, {"HYPERSHIFT_BINARY": str(binary_path)}):
            result = get_hypershift_binary()

        assert result == str(binary_path)

    def test_get_hypershift_binary_env_not_file(self, tmp_path):
        """When HYPERSHIFT_BINARY points to non-file it should check config."""
        with patch.dict(os.environ, {"HYPERSHIFT_BINARY": "/nonexistent/path"}):
            with patch("shutil.which", return_value=None):
                result = get_hypershift_binary()

        assert result is None

    def test_get_hypershift_binary_from_config(self, tmp_path):
        """When config has hypershift_binary it should return that path."""
        binary_path = tmp_path / "hypershift"
        binary_path.touch()

        mock_config = MagicMock()
        mock_config.get_hypershift_binary.return_value = str(binary_path)

        with patch.dict(os.environ, {}, clear=True):
            # Clear HYPERSHIFT_BINARY if set
            os.environ.pop("HYPERSHIFT_BINARY", None)
            result = get_hypershift_binary(config=mock_config)

        assert result == str(binary_path)

    def test_get_hypershift_binary_from_path(self):
        """When hypershift is in PATH it should return that path."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("HYPERSHIFT_BINARY", None)
            with patch("shutil.which", return_value="/usr/local/bin/hypershift"):
                result = get_hypershift_binary()

        assert result == "/usr/local/bin/hypershift"

    def test_get_hypershift_binary_not_found(self):
        """When hypershift is not found it should return None."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("HYPERSHIFT_BINARY", None)
            with patch("shutil.which", return_value=None):
                result = get_hypershift_binary()

        assert result is None


class TestCheckHypershiftInstalled:
    """Tests for check_hypershift_installed function."""

    def test_check_hypershift_installed_true(self):
        """When hypershift is found it should return True."""
        with patch(
            "gcphcp.utils.hypershift.get_hypershift_binary",
            return_value="/usr/local/bin/hypershift",
        ):
            assert check_hypershift_installed() is True

    def test_check_hypershift_installed_false(self):
        """When hypershift is not found it should return False."""
        with patch("gcphcp.utils.hypershift.get_hypershift_binary", return_value=None):
            assert check_hypershift_installed() is False


class TestValidateWifConfig:
    """Tests for validate_iam_config function."""

    def test_validate_iam_config_valid(self):
        """When WIF config has all required fields it should return True."""
        valid_config = {
            "projectId": "my-project",
            "projectNumber": "123456789",
            "infraId": "my-infra",
            "workloadIdentityPool": {
                "poolId": "my-pool",
                "providerId": "my-provider",
            },
            "serviceAccounts": {
                "ctrlplane-op": "sa1@example.com",
                "nodepool-mgmt": "sa2@example.com",
                "cloud-controller": "sa3@example.com",
                "gcp-pd-csi": "sa4@example.com",
                "image-registry": "sa5@example.com",
                "cloud-network": "sa6@example.com",
            },
        }

        assert validate_iam_config(valid_config) is True

    def test_validate_iam_config_missing_project_id(self):
        """When WIF config is missing projectId it should return False."""
        invalid_config = {
            "projectNumber": "123456789",
            "infraId": "my-infra",
            "workloadIdentityPool": {
                "poolId": "my-pool",
                "providerId": "my-provider",
            },
            "serviceAccounts": {
                "ctrlplane-op": "sa1@example.com",
                "nodepool-mgmt": "sa2@example.com",
            },
        }

        assert validate_iam_config(invalid_config) is False

    def test_validate_iam_config_missing_pool_id(self):
        """When WIF config is missing poolId it should return False."""
        invalid_config = {
            "projectId": "my-project",
            "projectNumber": "123456789",
            "infraId": "my-infra",
            "workloadIdentityPool": {
                "providerId": "my-provider",
            },
            "serviceAccounts": {
                "ctrlplane-op": "sa1@example.com",
                "nodepool-mgmt": "sa2@example.com",
            },
        }

        assert validate_iam_config(invalid_config) is False

    def test_validate_iam_config_missing_service_account(self):
        """When WIF config is missing service account it should return False."""
        invalid_config = {
            "projectId": "my-project",
            "projectNumber": "123456789",
            "infraId": "my-infra",
            "workloadIdentityPool": {
                "poolId": "my-pool",
                "providerId": "my-provider",
            },
            "serviceAccounts": {
                "ctrlplane-op": "sa1@example.com",
                # Missing nodepool-mgmt
            },
        }

        assert validate_iam_config(invalid_config) is False

    def test_validate_iam_config_empty(self):
        """When WIF config is empty it should return False."""
        assert validate_iam_config({}) is False


class TestWifConfigToClusterSpec:
    """Tests for iam_config_to_wif_spec function."""

    def test_iam_config_to_wif_spec_conversion(self):
        """When converting WIF config it should produce correct cluster spec."""
        wif_config = {
            "projectId": "my-project",
            "projectNumber": "123456789",
            "infraId": "my-infra",
            "workloadIdentityPool": {
                "poolId": "my-pool",
                "providerId": "my-provider",
            },
            "serviceAccounts": {
                "ctrlplane-op": "ctrlplane@example.com",
                "nodepool-mgmt": "nodepool@example.com",
                "cloud-controller": "cloudcontroller@example.com",
                "gcp-pd-csi": "storage@example.com",
                "image-registry": "imageregistry@example.com",
                "cloud-network": "cloudnetwork@example.com",
            },
        }

        result = iam_config_to_wif_spec(wif_config)

        assert result["projectNumber"] == "123456789"
        assert result["poolID"] == "my-pool"
        assert result["providerID"] == "my-provider"
        ctrl_email = result["serviceAccountsRef"]["controlPlaneEmail"]
        assert ctrl_email == "ctrlplane@example.com"
        assert result["serviceAccountsRef"]["nodePoolEmail"] == "nodepool@example.com"
        ccm_email = result["serviceAccountsRef"]["cloudControllerEmail"]
        assert ccm_email == "cloudcontroller@example.com"
        assert result["serviceAccountsRef"]["storageEmail"] == "storage@example.com"
        assert (
            result["serviceAccountsRef"]["imageRegistryEmail"]
            == "imageregistry@example.com"
        )
        assert (
            result["serviceAccountsRef"]["networkEmail"] == "cloudnetwork@example.com"
        )

    def test_iam_config_to_wif_spec_empty_config(self):
        """When converting empty config it should return None values."""
        result = iam_config_to_wif_spec({})

        assert result["projectNumber"] is None
        assert result["poolID"] is None
        assert result["providerID"] is None


class TestHypershiftError:
    """Tests for HypershiftError exception."""

    def test_hypershift_error_message(self):
        """When raising HypershiftError it should contain the message."""
        with pytest.raises(HypershiftError) as exc_info:
            raise HypershiftError("Test error message")

        assert "Test error message" in str(exc_info.value)


class TestRequireHypershiftBinary:
    """Tests for require_hypershift_binary function."""

    def test_require_hypershift_binary_found(self, tmp_path):
        """When hypershift is found it should return the path."""
        binary_path = tmp_path / "hypershift"
        binary_path.touch()

        with patch.dict(os.environ, {"HYPERSHIFT_BINARY": str(binary_path)}):
            result = require_hypershift_binary()

        assert result == str(binary_path)

    def test_require_hypershift_binary_not_found(self):
        """When hypershift is not found it should raise HypershiftError."""
        with patch("gcphcp.utils.hypershift.get_hypershift_binary", return_value=None):
            with pytest.raises(HypershiftError) as exc_info:
                require_hypershift_binary()

        assert "hypershift CLI not found" in str(exc_info.value)


class TestValidateInfraIdLength:
    """Tests for validate_infra_id_length function."""

    def test_validate_infra_id_length_valid(self):
        """When infra ID is within limit it should not raise."""
        # Should not raise
        validate_infra_id_length("my-infra")
        validate_infra_id_length("a" * MAX_INFRA_ID_LENGTH)

    def test_validate_infra_id_length_too_long(self):
        """When infra ID exceeds limit it should raise ValueError."""
        long_id = "a" * (MAX_INFRA_ID_LENGTH + 1)
        with pytest.raises(ValueError) as exc_info:
            validate_infra_id_length(long_id)

        assert "too long" in str(exc_info.value)
        assert str(MAX_INFRA_ID_LENGTH) in str(exc_info.value)


class TestValidateInfraId:
    """Tests for validate_infra_id function."""

    def test_validate_infra_id_valid_short(self):
        """When infra ID is valid and short it should not raise."""
        validate_infra_id("my-infra")

    def test_validate_infra_id_valid_single_char(self):
        """When infra ID is a single lowercase letter it should not raise."""
        validate_infra_id("a")

    def test_validate_infra_id_valid_max_length(self):
        """When infra ID is exactly max length it should not raise."""
        validate_infra_id("a" * MAX_INFRA_ID_LENGTH)

    def test_validate_infra_id_valid_with_digits(self):
        """When infra ID starts with letter and contains digits it should not raise."""
        validate_infra_id("my-cluster-01")

    def test_validate_infra_id_valid_all_lowercase(self):
        """When infra ID is all lowercase letters it should not raise."""
        validate_infra_id("abcdef")

    def test_validate_infra_id_starts_with_digit(self):
        """When infra ID starts with a digit it should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_infra_id("1my-infra")

        assert "must start with a lowercase letter" in str(exc_info.value)

    def test_validate_infra_id_starts_with_digit_uuid(self):
        """When infra ID is a UUID starting with a digit it should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_infra_id("04e6fe60")

        assert "must start with a lowercase letter" in str(exc_info.value)

    def test_validate_infra_id_uppercase(self):
        """When infra ID contains uppercase letters it should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_infra_id("My-Infra")

        assert "must start with a lowercase letter" in str(exc_info.value)

    def test_validate_infra_id_underscore(self):
        """When infra ID contains underscores it should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_infra_id("my_infra")

        assert "must start with a lowercase letter" in str(exc_info.value)

    def test_validate_infra_id_too_long(self):
        """When infra ID exceeds max length it should raise ValueError."""
        long_id = "a" * (MAX_INFRA_ID_LENGTH + 1)
        with pytest.raises(ValueError) as exc_info:
            validate_infra_id(long_id)

        assert "too long" in str(exc_info.value)

    def test_validate_infra_id_empty(self):
        """When infra ID is empty it should raise ValueError."""
        with pytest.raises(ValueError):
            validate_infra_id("")

    def test_validate_infra_id_starts_with_hyphen(self):
        """When infra ID starts with a hyphen it should raise ValueError."""
        with pytest.raises(ValueError):
            validate_infra_id("-my-infra")

    def test_infra_id_pattern_constant_exists(self):
        """The INFRA_ID_PATTERN constant should be the expected regex."""
        assert INFRA_ID_PATTERN == r"^[a-z][-a-z0-9]*$"


class TestValidateInfraConfig:
    """Tests for validate_infra_config function."""

    def test_validate_infra_config_valid(self):
        """When infra config has all required fields it should return True."""
        valid_config = {
            "projectId": "my-project",
            "infraId": "my-infra",
            "region": "us-central1",
            "networkName": "my-network",
            "subnetName": "my-subnet",
        }

        assert validate_infra_config(valid_config) is True

    def test_validate_infra_config_missing_network(self):
        """When infra config is missing networkName it should return False."""
        invalid_config = {
            "projectId": "my-project",
            "infraId": "my-infra",
            "region": "us-central1",
            "subnetName": "my-subnet",
        }

        assert validate_infra_config(invalid_config) is False

    def test_validate_infra_config_empty(self):
        """When infra config is empty it should return False."""
        assert validate_infra_config({}) is False


class TestServiceAccountsConstant:
    """Tests for SERVICE_ACCOUNTS constant."""

    def test_service_accounts_has_required_keys(self):
        """When checking SERVICE_ACCOUNTS it should have required keys."""
        assert "ctrlplane-op" in SERVICE_ACCOUNTS
        assert "nodepool-mgmt" in SERVICE_ACCOUNTS
        assert "cloud-controller" in SERVICE_ACCOUNTS
        assert "gcp-pd-csi" in SERVICE_ACCOUNTS
        assert "image-registry" in SERVICE_ACCOUNTS
        assert "cloud-network" in SERVICE_ACCOUNTS

    def test_service_accounts_values_are_strings(self):
        """When checking SERVICE_ACCOUNTS values they should be strings."""
        for key, value in SERVICE_ACCOUNTS.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


class TestDestroyIamGcp:
    """Tests for destroy_iam_gcp function."""

    def test_destroy_iam_gcp_success(self):
        """When destroy succeeds it should return True."""
        with patch(
            "gcphcp.utils.hypershift.require_hypershift_binary",
            return_value="/usr/local/bin/hypershift",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = destroy_iam_gcp(
                    infra_id="test-infra",
                    project_id="test-project",
                )

        assert result is True
        mock_run.assert_called_once()

    def test_destroy_iam_gcp_timeout(self):
        """When destroy times out it should raise HypershiftError."""
        with patch(
            "gcphcp.utils.hypershift.require_hypershift_binary",
            return_value="/usr/local/bin/hypershift",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(
                    cmd="test", timeout=300
                )

                with pytest.raises(HypershiftError) as exc_info:
                    destroy_iam_gcp(
                        infra_id="test-infra",
                        project_id="test-project",
                    )

        assert "timed out" in str(exc_info.value)

    def test_destroy_iam_gcp_command_error(self):
        """When destroy command fails it should raise HypershiftError."""
        with patch(
            "gcphcp.utils.hypershift.require_hypershift_binary",
            return_value="/usr/local/bin/hypershift",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(
                    returncode=1, cmd="test", stderr="Command failed"
                )

                with pytest.raises(HypershiftError) as exc_info:
                    destroy_iam_gcp(
                        infra_id="test-infra",
                        project_id="test-project",
                    )

        assert "Command failed" in str(exc_info.value)


class TestDestroyInfraGcp:
    """Tests for destroy_infra_gcp function."""

    def test_destroy_infra_gcp_success(self):
        """When destroy succeeds it should return True."""
        with patch(
            "gcphcp.utils.hypershift.require_hypershift_binary",
            return_value="/usr/local/bin/hypershift",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = destroy_infra_gcp(
                    infra_id="test-infra",
                    project_id="test-project",
                    region="us-central1",
                )

        assert result is True
        mock_run.assert_called_once()

    def test_destroy_infra_gcp_timeout(self):
        """When destroy times out it should raise HypershiftError."""
        with patch(
            "gcphcp.utils.hypershift.require_hypershift_binary",
            return_value="/usr/local/bin/hypershift",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(
                    cmd="test", timeout=300
                )

                with pytest.raises(HypershiftError) as exc_info:
                    destroy_infra_gcp(
                        infra_id="test-infra",
                        project_id="test-project",
                        region="us-central1",
                    )

        assert "timed out" in str(exc_info.value)
