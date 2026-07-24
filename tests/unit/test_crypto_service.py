"""
Unit tests for CryptoService.
Covers: RSA encrypt/decrypt round-trip, SHA-256 integrity hash verify/tamper-detect,
anonymise_voter determinism, receipt ID format.
NFR-013: 100% of cryptographic operations covered by automated unit tests.
"""
import pytest
import json
from app.services.crypto_service import CryptoService


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate one key pair shared across this module's tests."""
    return CryptoService.generate_rsa_keypair()


class TestKeyGeneration:
    def test_generates_pem_strings(self, rsa_keypair):
        public_pem, private_pem = rsa_keypair
        assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
        assert private_pem.startswith("-----BEGIN RSA PRIVATE KEY-----")

    def test_public_and_private_are_different(self, rsa_keypair):
        public_pem, private_pem = rsa_keypair
        assert public_pem != private_pem


class TestBallotEncryption:
    def test_encrypt_returns_base64_string(self, rsa_keypair):
        public_pem, _ = rsa_keypair
        selections = {"1": 101, "2": 202}
        ciphertext = CryptoService.encrypt_ballot(selections, public_pem)
        assert isinstance(ciphertext, str)
        assert len(ciphertext) > 50

    def test_encrypt_decrypt_round_trip(self, rsa_keypair):
        """Encrypt → Decrypt must reproduce the original selections dict."""
        public_pem, private_pem = rsa_keypair
        original = {"1": 101, "2": 202, "3": 303}
        ciphertext = CryptoService.encrypt_ballot(original, public_pem)
        recovered = CryptoService.decrypt_ballot(ciphertext, private_pem)
        assert recovered == original

    def test_different_plaintexts_produce_different_ciphertexts(self, rsa_keypair):
        """OAEP uses random padding, so even the same plaintext differs each call."""
        public_pem, _ = rsa_keypair
        s = {"1": 1}
        c1 = CryptoService.encrypt_ballot(s, public_pem)
        c2 = CryptoService.encrypt_ballot(s, public_pem)
        assert c1 != c2  # Probabilistic encryption

    def test_wrong_key_raises_on_decrypt(self, rsa_keypair):
        """Decrypting with a different private key must raise an exception."""
        public_pem, _ = rsa_keypair
        _, other_private_pem = CryptoService.generate_rsa_keypair()
        ciphertext = CryptoService.encrypt_ballot({"1": 1}, public_pem)
        with pytest.raises(Exception):
            CryptoService.decrypt_ballot(ciphertext, other_private_pem)

    def test_empty_selections_encrypt_decrypt(self, rsa_keypair):
        """Edge case: empty selection dict should still round-trip cleanly."""
        public_pem, private_pem = rsa_keypair
        ciphertext = CryptoService.encrypt_ballot({}, public_pem)
        recovered = CryptoService.decrypt_ballot(ciphertext, private_pem)
        assert recovered == {}


class TestIntegrityHash:
    ANON_REF = "abc123def456"
    ELECTION_ID = 7
    TIMESTAMP = "2025-01-15T10:00:00+00:00"
    CIPHERTEXT = "base64ciphertext=="

    def test_hash_is_64_char_hex(self):
        h = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_verify_passes_for_correct_inputs(self):
        h = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        assert CryptoService.verify_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT, h
        )

    def test_verify_fails_if_ciphertext_tampered(self):
        h = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        tampered = self.CIPHERTEXT[:-1] + "X"
        assert not CryptoService.verify_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, tampered, h
        )

    def test_verify_fails_if_election_id_changed(self):
        h = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        assert not CryptoService.verify_ballot_hash(
            self.ANON_REF, self.ELECTION_ID + 1, self.TIMESTAMP, self.CIPHERTEXT, h
        )

    def test_verify_fails_if_timestamp_changed(self):
        h = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        assert not CryptoService.verify_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, "2099-01-01T00:00:00+00:00", self.CIPHERTEXT, h
        )

    def test_verify_fails_if_voter_ref_changed(self):
        h = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        assert not CryptoService.verify_ballot_hash(
            "different_voter_ref", self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT, h
        )

    def test_deterministic_hash(self):
        """Same inputs must always produce the same hash."""
        h1 = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        h2 = CryptoService.compute_ballot_hash(
            self.ANON_REF, self.ELECTION_ID, self.TIMESTAMP, self.CIPHERTEXT
        )
        assert h1 == h2


class TestAnonymiseVoter:
    def test_returns_64_char_hex(self):
        ref = CryptoService.anonymise_voter(42, 7, "some-salt")
        assert len(ref) == 64

    def test_deterministic(self):
        r1 = CryptoService.anonymise_voter(42, 7, "salt")
        r2 = CryptoService.anonymise_voter(42, 7, "salt")
        assert r1 == r2

    def test_different_users_produce_different_refs(self):
        r1 = CryptoService.anonymise_voter(1, 7, "salt")
        r2 = CryptoService.anonymise_voter(2, 7, "salt")
        assert r1 != r2

    def test_different_elections_produce_different_refs(self):
        r1 = CryptoService.anonymise_voter(42, 1, "salt")
        r2 = CryptoService.anonymise_voter(42, 2, "salt")
        assert r1 != r2

    def test_different_salts_produce_different_refs(self):
        r1 = CryptoService.anonymise_voter(42, 7, "salt-a")
        r2 = CryptoService.anonymise_voter(42, 7, "salt-b")
        assert r1 != r2


class TestReceiptId:
    def test_is_40_char_hex(self):
        rid = CryptoService.generate_receipt_id()
        assert len(rid) == 40
        assert all(c in "0123456789abcdef" for c in rid)

    def test_unique(self):
        ids = {CryptoService.generate_receipt_id() for _ in range(100)}
        assert len(ids) == 100  # All unique
