class MaskedApiKey {
  final String maskedKey;
  final String? label;

  MaskedApiKey({required this.maskedKey, this.label});

  factory MaskedApiKey.fromJson(Map<String, dynamic> json) {
    return MaskedApiKey(
      maskedKey: json['masked_key'] as String? ?? '',
      label: json['label'] as String?,
    );
  }
}

class AppSettings {
  final String llmProvider;
  final String llmBaseUrl;
  final List<MaskedApiKey> llmApiKeys;
  final String llmKeyStrategy;
  final String llmModel;
  final String llmStructuredMode;
  final bool llmSupportsTools;
  final int llmDailyTokenCap;
  final bool privacyRedactPii;

  AppSettings({
    required this.llmProvider,
    required this.llmBaseUrl,
    required this.llmApiKeys,
    required this.llmKeyStrategy,
    required this.llmModel,
    required this.llmStructuredMode,
    required this.llmSupportsTools,
    required this.llmDailyTokenCap,
    required this.privacyRedactPii,
  });

  factory AppSettings.fromJson(Map<String, dynamic> json) {
    final rawKeys = json['llm_api_keys'] as List<dynamic>? ?? [];
    return AppSettings(
      llmProvider: json['llm_provider'] as String? ?? 'groq',
      llmBaseUrl: json['llm_base_url'] as String? ?? 'https://api.groq.com/openai/v1',
      llmApiKeys: rawKeys.map((k) => MaskedApiKey.fromJson(k as Map<String, dynamic>)).toList(),
      llmKeyStrategy: json['llm_key_strategy'] as String? ?? 'failover',
      llmModel: json['llm_model'] as String? ?? '',
      llmStructuredMode: json['llm_structured_mode'] as String? ?? 'auto',
      llmSupportsTools: json['llm_supports_tools'] as bool? ?? true,
      llmDailyTokenCap: json['llm_daily_token_cap'] as int? ?? 200000,
      privacyRedactPii: json['privacy_redact_pii'] as bool? ?? true,
    );
  }
}

class ProbeResult {
  final String label;
  final String status;
  final bool authOk;
  final int latencyMs;
  final String detectedStructuredMode;
  final bool supportsTools;
  final bool hasUsage;
  final bool hasReasoningTags;
  final String? message;

  ProbeResult({
    required this.label,
    required this.status,
    required this.authOk,
    required this.latencyMs,
    required this.detectedStructuredMode,
    required this.supportsTools,
    required this.hasUsage,
    required this.hasReasoningTags,
    this.message,
  });

  factory ProbeResult.fromJson(Map<String, dynamic> json) {
    return ProbeResult(
      label: json['label'] as String? ?? '',
      status: json['status'] as String? ?? 'error',
      authOk: json['auth_ok'] as bool? ?? false,
      latencyMs: json['latency_ms'] as int? ?? 0,
      detectedStructuredMode: json['detected_structured_mode'] as String? ?? 'none',
      supportsTools: json['supports_tools'] as bool? ?? false,
      hasUsage: json['has_usage'] as bool? ?? false,
      hasReasoningTags: json['has_reasoning_tags'] as bool? ?? false,
      message: json['message'] as String?,
    );
  }
}

class TestLlmResult {
  final bool success;
  final List<ProbeResult> probes;

  TestLlmResult({required this.success, required this.probes});

  factory TestLlmResult.fromJson(Map<String, dynamic> json) {
    final rawProbes = json['probes'] as List<dynamic>? ?? [];
    return TestLlmResult(
      success: json['success'] as bool? ?? false,
      probes: rawProbes.map((p) => ProbeResult.fromJson(p as Map<String, dynamic>)).toList(),
    );
  }
}

class UsageStats {
  final int tokensToday;
  final int callsToday;
  final int rateLimitedDocuments;

  UsageStats({
    required this.tokensToday,
    required this.callsToday,
    required this.rateLimitedDocuments,
  });

  factory UsageStats.fromJson(Map<String, dynamic> json) {
    return UsageStats(
      tokensToday: json['tokens_today'] as int? ?? 0,
      callsToday: json['calls_today'] as int? ?? 0,
      rateLimitedDocuments: json['rate_limited_documents'] as int? ?? 0,
    );
  }
}
