"""
CryptoService — all cryptographic operations in one place.
Strategy-pattern friendly: swap RSA for ECC by subclassing or injecting
a different provider without touching BallotService.

Algorithms used (matching the research paper):
  - RSA-2048, OAEP padding, SHA-256 hash (PyCryptodome)
  - SHA-256 for ballot integrity hash
"""
import base64
import hashlib
import json
import os
import secrets
from typing import Tuple

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256


class CryptoService:
    # ── RSA Key Generation ─────────────────────────────────────────────────

    @staticmethod
    def generate_rsa_keypair(bits: int = 2048) -> Tuple[str, str]:
        """
        Generate an RSA key pair.

        Returns:
            (public_pem, private_pem) as UTF-8 strings.
        The private PEM is exported ONCE; the caller must persist it securely
        and NOT store it in the database.
        """
        key = RSA.generate(bits)
        private_pem = key.export_key("PEM").decode("utf-8")
        public_pem = key.publickey().export_key("PEM").decode("utf-8")
        return public_pem, private_pem

    @staticmethod
    def export_private_key_encrypted(private_pem: str, passphrase: str) -> str:
        """
        Re-export the private key with AES-256-CBC passphrase protection.
        Returns the protected PEM string.
        """
        key = RSA.import_key(private_pem.encode("utf-8"))
        return key.export_key(
            "PEM",
            passphrase=passphrase.encode("utf-8"),
            pkcs=8,
            protection="PBKDF2WithHMAC-SHA1AndAES256-CBC",
        ).decode("utf-8")

    # ── Ballot Encryption ─────────────────────────────────────────────────

    @staticmethod
    def encrypt_ballot(selections: dict, public_pem: str) -> str:
        """
        Serialize and encrypt a ballot.

        Args:
            selections: {position_id: candidate_id, ...}
            public_pem: Election's RSA-2048 public key in PEM format.

        Returns:
            Base64-encoded RSA-OAEP ciphertext string.
        """
        plaintext = json.dumps(selections, sort_keys=True).encode("utf-8")
        public_key = RSA.import_key(public_pem.encode("utf-8"))
        cipher = PKCS1_OAEP.new(public_key, hashAlgo=SHA256)
        ciphertext = cipher.encrypt(plaintext)
        return base64.b64encode(ciphertext).decode("utf-8")

    @staticmethod
    def decrypt_ballot(encrypted_b64: str, private_pem: str, passphrase: str = "") -> dict:
        """
        Decrypt a ballot ciphertext.

        Args:
            encrypted_b64: Base64-encoded ciphertext.
            private_pem: Admin-held private key PEM (may be passphrase-protected).
            passphrase: Passphrase if the private key is encrypted; empty string if not.

        Returns:
            Parsed selections dict {position_id: candidate_id}.
        """
        ciphertext = base64.b64decode(encrypted_b64.encode("utf-8"))
        kwargs = {}
        if passphrase:
            kwargs["passphrase"] = passphrase.encode("utf-8")
        private_key = RSA.import_key(private_pem.encode("utf-8"), **kwargs)
        cipher = PKCS1_OAEP.new(private_key, hashAlgo=SHA256)
        plaintext = cipher.decrypt(ciphertext)
        return json.loads(plaintext.decode("utf-8"))

    # ── Integrity Hash ────────────────────────────────────────────────────

    @staticmethod
    def compute_ballot_hash(
        anonymised_voter_ref: str,
        election_id: int,
        timestamp_iso: str,
        ciphertext_b64: str,
    ) -> str:
        """
        Compute the SHA-256 integrity hash over the canonical ballot fields.

        Input format: anonymised_voter_ref || "|" || election_id || "|"
                      || timestamp_iso || "|" || ciphertext_b64
        """
        payload = (
            f"{anonymised_voter_ref}|{election_id}|{timestamp_iso}|{ciphertext_b64}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_ballot_hash(
        anonymised_voter_ref: str,
        election_id: int,
        timestamp_iso: str,
        ciphertext_b64: str,
        expected_hash: str,
    ) -> bool:
        """Recompute and compare the ballot's integrity hash."""
        actual = CryptoService.compute_ballot_hash(
            anonymised_voter_ref, election_id, timestamp_iso, ciphertext_b64
        )
        return secrets.compare_digest(actual, expected_hash)

    # ── Voter Anonymisation ───────────────────────────────────────────────

    @staticmethod
    def anonymise_voter(user_id: int, election_id: int, salt: str) -> str:
        """
        One-way, salted hash of (user_id, election_id).
        Stored in ballots.anonymised_voter_ref — never reveals which voter
        owns which ballot, but allows the server to detect duplicates
        BEFORE the ballot is written (by checking eligible_voters.has_voted).
        """
        payload = f"{salt}:{user_id}:{election_id}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ── Receipt ID ────────────────────────────────────────────────────────

    @staticmethod
    def generate_receipt_id() -> str:
        """40-character hex receipt identifier (20 random bytes)."""
        return secrets.token_hex(20)
