import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('Initialize sharedPreferencesProvider in main');
});

final localCacheServiceProvider = Provider<LocalCacheService>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return LocalCacheService(prefs);
});

class LocalCacheService {
  final SharedPreferences _prefs;

  static const String _docsKey = 'cache_documents_list_v1';
  static const String _labsKey = 'cache_labs_summary_v1';
  static const String _askKey = 'cache_ask_history_v1';

  LocalCacheService(this._prefs);

  Future<void> cacheDocuments(List<Map<String, dynamic>> docs) async {
    final raw = jsonEncode(docs);
    await _prefs.setString(_docsKey, raw);
  }

  Future<List<Map<String, dynamic>>> getCachedDocuments() async {
    final raw = _prefs.getString(_docsKey);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list.map((e) => e as Map<String, dynamic>).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> cacheLabs(List<Map<String, dynamic>> labs) async {
    final raw = jsonEncode(labs);
    await _prefs.setString(_labsKey, raw);
  }

  Future<List<Map<String, dynamic>>> getCachedLabs() async {
    final raw = _prefs.getString(_labsKey);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list.map((e) => e as Map<String, dynamic>).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> cacheAskHistory(List<Map<String, dynamic>> messages) async {
    final raw = jsonEncode(messages);
    await _prefs.setString(_askKey, raw);
  }

  Future<List<Map<String, dynamic>>> getCachedAskHistory() async {
    final raw = _prefs.getString(_askKey);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list.map((e) => e as Map<String, dynamic>).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> clearAskHistory() async {
    await _prefs.remove(_askKey);
  }
}
