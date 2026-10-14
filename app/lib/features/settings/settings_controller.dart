import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import 'settings_model.dart';

class SettingsState {
  final AsyncValue<AppSettings> settings;
  final AsyncValue<List<String>> models;
  final AsyncValue<UsageStats?> usage;
  final AsyncValue<TestLlmResult?> testResult;
  final bool isTesting;

  SettingsState({
    required this.settings,
    required this.models,
    required this.usage,
    required this.testResult,
    this.isTesting = false,
  });

  SettingsState copyWith({
    AsyncValue<AppSettings>? settings,
    AsyncValue<List<String>>? models,
    AsyncValue<UsageStats?>? usage,
    AsyncValue<TestLlmResult?>? testResult,
    bool? isTesting,
  }) {
    return SettingsState(
      settings: settings ?? this.settings,
      models: models ?? this.models,
      usage: usage ?? this.usage,
      testResult: testResult ?? this.testResult,
      isTesting: isTesting ?? this.isTesting,
    );
  }
}

class SettingsController extends StateNotifier<SettingsState> {
  final ApiClient _apiClient;

  SettingsController(this._apiClient)
      : super(
          SettingsState(
            settings: const AsyncValue.loading(),
            models: const AsyncValue.data([]),
            usage: const AsyncValue.data(null),
            testResult: const AsyncValue.data(null),
          ),
        ) {
    loadAll();
  }

  Future<void> loadAll() async {
    await loadSettings();
    await loadModels();
    await loadUsage();
  }

  Future<void> loadSettings() async {
    try {
      final res = await _apiClient.dio.get('/settings');
      final appSettings = AppSettings.fromJson(res.data);
      state = state.copyWith(settings: AsyncValue.data(appSettings));
    } catch (e, st) {
      state = state.copyWith(settings: AsyncValue.error(e, st));
    }
  }

  Future<void> loadModels() async {
    try {
      final res = await _apiClient.dio.get('/settings/models');
      final list = (res.data as List<dynamic>).map((e) => e.toString()).toList();
      state = state.copyWith(models: AsyncValue.data(list));
    } catch (e, st) {
      state = state.copyWith(models: AsyncValue.error(e, st));
    }
  }

  Future<void> loadUsage() async {
    try {
      final res = await _apiClient.dio.get('/usage');
      final stats = UsageStats.fromJson(res.data);
      state = state.copyWith(usage: AsyncValue.data(stats));
    } catch (e, st) {
      state = state.copyWith(usage: AsyncValue.error(e, st));
    }
  }

  Future<void> updateSettings(Map<String, dynamic> updatePayload) async {
    state = state.copyWith(settings: const AsyncValue.loading());
    try {
      final res = await _apiClient.dio.put('/settings', data: updatePayload);
      final updated = AppSettings.fromJson(res.data);
      state = state.copyWith(settings: AsyncValue.data(updated));
      await loadModels();
    } catch (e, st) {
      state = state.copyWith(settings: AsyncValue.error(e, st));
    }
  }

  Future<void> testConnection() async {
    state = state.copyWith(isTesting: true, testResult: const AsyncValue.loading());
    try {
      final res = await _apiClient.dio.post('/settings/test-llm');
      final result = TestLlmResult.fromJson(res.data);
      state = state.copyWith(isTesting: false, testResult: AsyncValue.data(result));
    } catch (e, st) {
      state = state.copyWith(isTesting: false, testResult: AsyncValue.error(e, st));
    }
  }
}

final settingsControllerProvider =
    StateNotifierProvider<SettingsController, SettingsState>((ref) {
  final client = ref.watch(apiClientProvider);
  return SettingsController(client);
});
