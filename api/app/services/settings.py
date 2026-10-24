from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.models import UserSetting, User
from app.config import get_settings
from app.security.crypto import encrypt_for_user, decrypt_for_user
from app.schemas import AppSettingsRead, AppSettingsUpdate, MaskedApiKeyEntry

PROVIDER_PRESETS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
    "mistral": "https://api.mistral.ai/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
}


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 6:
        return "••••" + key[-2:]
    return "••••" + key[-4:]


class SettingsService:
    def __init__(self, db: Session, user_id: int = 1):
        self.db = db
        self.user_id = user_id
        self.env = get_settings()

    def is_user_admin(self) -> bool:
        user = self.db.query(User).filter(User.id == self.user_id).first()
        return bool(user and user.is_admin)

    def get_raw_settings(self) -> Dict[str, Any]:
        records = (
            self.db.query(UserSetting)
            .filter(UserSetting.user_id == self.user_id)
            .all()
        )
        data = {record.key: record.value for record in records}
        return data

    def get_setting_value(self, key: str, default: Any = None) -> Any:
        record = (
            self.db.query(UserSetting)
            .filter(UserSetting.user_id == self.user_id, UserSetting.key == key)
            .first()
        )
        if record:
            return record.value
        return default

    def set_setting_value(self, key: str, value: Any, is_secret: bool = False):
        record = (
            self.db.query(UserSetting)
            .filter(UserSetting.user_id == self.user_id, UserSetting.key == key)
            .first()
        )
        if record:
            record.value = value
            record.is_secret = is_secret
        else:
            record = UserSetting(user_id=self.user_id, key=key, value=value, is_secret=is_secret)
            self.db.add(record)
        self.db.commit()

    def get_read_settings(self) -> AppSettingsRead:
        raw = self.get_raw_settings()

        # Provider
        provider = raw.get("llm.provider", "groq")

        # Base URL fallback
        base_url = raw.get("llm.base_url")
        if not base_url:
            base_url = self.env.LLM_BASE_URL or PROVIDER_PRESETS.get(provider, "https://api.groq.com/openai/v1")

        # Keys (encrypted in DB with user's key)
        encrypted_keys = raw.get("llm.api_keys", [])
        masked_keys = []
        if encrypted_keys:
            for item in encrypted_keys:
                enc_key = item.get("key", "")
                try:
                    dec = decrypt_for_user(enc_key, self.user_id)
                    masked = mask_key(dec)
                except Exception:
                    masked = "••••(invalid)"
                masked_keys.append(MaskedApiKeyEntry(masked_key=masked, label=item.get("label")))
        else:
            # Fallback to env ONLY for admin
            if self.is_user_admin():
                env_key = self.env.GROQ_API_KEY if provider == "groq" and self.env.GROQ_API_KEY else self.env.LLM_API_KEY
                if env_key:
                    for k in env_key.split(","):
                        k = k.strip()
                        if k:
                            masked_keys.append(MaskedApiKeyEntry(masked_key=mask_key(k), label="env"))

        model = raw.get("llm.model") or self.env.LLM_MODEL or ""

        return AppSettingsRead(
            llm_provider=provider,
            llm_base_url=base_url,
            llm_api_keys=masked_keys,
            llm_key_strategy=raw.get("llm.key_strategy", "failover"),
            llm_model=model,
            llm_model_extract=raw.get("llm.model_extract"),
            llm_model_ask=raw.get("llm.model_ask"),
            llm_structured_mode=raw.get("llm.structured_mode", "auto"),
            llm_supports_tools=raw.get("llm.supports_tools", True),
            llm_max_tokens_param=raw.get("llm.max_tokens_param", "max_tokens"),
            llm_extra_params=raw.get("llm.extra_params", {}),
            llm_extra_headers=raw.get("llm.extra_headers", {}),
            llm_strip_reasoning=raw.get("llm.strip_reasoning", True),
            llm_concurrency=raw.get("llm.concurrency", 2),
            llm_timeout_s=raw.get("llm.timeout_s", 60),
            llm_max_output_tokens=raw.get("llm.max_output_tokens", 2000),
            llm_daily_token_cap=raw.get("llm.daily_token_cap", 200000),
            privacy_redact_pii=raw.get("privacy.redact_pii", True),
            ocr_languages=raw.get("ocr.languages", ["en"]),
            embed_model=raw.get("embed.model", "multilingual-e5-small"),
        )

    def get_decrypted_keys(self) -> List[Dict[str, str]]:
        raw = self.get_raw_settings()
        encrypted_keys = raw.get("llm.api_keys", [])
        decrypted = []
        if encrypted_keys:
            for item in encrypted_keys:
                enc_key = item.get("key", "")
                try:
                    dec = decrypt_for_user(enc_key, self.user_id)
                    if dec:
                        decrypted.append({"key": dec, "label": item.get("label", "key")})
                except Exception:
                    continue
        else:
            # Fallback to env ONLY for admin
            if self.is_user_admin():
                provider = raw.get("llm.provider", "groq")
                env_key = self.env.GROQ_API_KEY if provider == "groq" and self.env.GROQ_API_KEY else self.env.LLM_API_KEY
                if env_key:
                    for idx, k in enumerate(env_key.split(",")):
                        k = k.strip()
                        if k:
                            decrypted.append({"key": k, "label": f"env-{idx+1}"})
        return decrypted

    def update_settings(self, update: AppSettingsUpdate) -> AppSettingsRead:
        if update.llm_provider is not None:
            self.set_setting_value("llm.provider", update.llm_provider)
        if update.llm_base_url is not None:
            self.set_setting_value("llm.base_url", update.llm_base_url)

        if update.llm_api_keys is not None:
            encrypted_list = []
            for item in update.llm_api_keys:
                if item.key:
                    enc = encrypt_for_user(item.key, self.user_id)
                    encrypted_list.append({"key": enc, "label": item.label or "default"})
            self.set_setting_value("llm.api_keys", encrypted_list, is_secret=True)

        if update.llm_key_strategy is not None:
            self.set_setting_value("llm.key_strategy", update.llm_key_strategy)
        if update.llm_model is not None:
            self.set_setting_value("llm.model", update.llm_model)
        if update.llm_model_extract is not None:
            self.set_setting_value("llm.model_extract", update.llm_model_extract)
        if update.llm_model_ask is not None:
            self.set_setting_value("llm.model_ask", update.llm_model_ask)
        if update.llm_structured_mode is not None:
            self.set_setting_value("llm.structured_mode", update.llm_structured_mode)
        if update.llm_supports_tools is not None:
            self.set_setting_value("llm.supports_tools", update.llm_supports_tools)
        if update.llm_max_tokens_param is not None:
            self.set_setting_value("llm.max_tokens_param", update.llm_max_tokens_param)
        if update.llm_extra_params is not None:
            self.set_setting_value("llm.extra_params", update.llm_extra_params)
        if update.llm_extra_headers is not None:
            self.set_setting_value("llm.extra_headers", update.llm_extra_headers)
        if update.llm_strip_reasoning is not None:
            self.set_setting_value("llm.strip_reasoning", update.llm_strip_reasoning)
        if update.llm_concurrency is not None:
            self.set_setting_value("llm.concurrency", update.llm_concurrency)
        if update.llm_timeout_s is not None:
            self.set_setting_value("llm.timeout_s", update.llm_timeout_s)
        if update.llm_max_output_tokens is not None:
            self.set_setting_value("llm.max_output_tokens", update.llm_max_output_tokens)
        if update.llm_daily_token_cap is not None:
            self.set_setting_value("llm.daily_token_cap", update.llm_daily_token_cap)
        if update.privacy_redact_pii is not None:
            self.set_setting_value("privacy.redact_pii", update.privacy_redact_pii)
        if update.ocr_languages is not None:
            self.set_setting_value("ocr.languages", update.ocr_languages)
        if update.embed_model is not None:
            self.set_setting_value("embed.model", update.embed_model)

        return self.get_read_settings()
