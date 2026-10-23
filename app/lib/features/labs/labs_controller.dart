import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/api_client.dart';
import '../../core/local_cache.dart';
import 'lab_model.dart';

const Set<String> kDefaultFavourites = {
  'HbA1c',
  'Fasting Glucose',
  'Hemoglobin',
  'Total Cholesterol',
};

class LabsController extends AsyncNotifier<List<LabTestSummary>> {
  @override
  Future<List<LabTestSummary>> build() async {
    return _fetchTests();
  }

  Future<List<LabTestSummary>> _fetchTests() async {
    final client = ref.read(apiClientProvider);
    final cache = ref.read(localCacheServiceProvider);
    try {
      final response = await client.dio.get('/tests');
      final data = response.data as List<dynamic>;
      final rawMaps = data.map((item) => item as Map<String, dynamic>).toList();
      await cache?.cacheLabs(rawMaps);
      return rawMaps
          .map((item) => LabTestSummary.fromJson(item))
          .toList();
    } catch (_) {
      final cached = await cache?.getCachedLabs() ?? [];
      if (cached.isNotEmpty) {
        return cached
            .map((item) => LabTestSummary.fromJson(item))
            .toList();
      }
      rethrow;
    }
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _fetchTests());
  }
}

final labsControllerProvider =
    AsyncNotifierProvider<LabsController, List<LabTestSummary>>(
  LabsController.new,
);

class LabFavouritesNotifier extends StateNotifier<Set<String>> {
  LabFavouritesNotifier(super.initial) {
    _loadFromPrefs();
  }

  static const String _prefsKey = 'lab_favourites';

  Future<void> _loadFromPrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final storedJson = prefs.getString(_prefsKey);
      if (storedJson != null) {
        final List<dynamic> decoded = jsonDecode(storedJson) as List<dynamic>;
        state = decoded.map((e) => e.toString()).toSet();
      } else {
        state = kDefaultFavourites;
      }
    } catch (_) {
      state = kDefaultFavourites;
    }
  }

  Future<void> toggle(String testName) async {
    final newSet = Set<String>.from(state);
    if (newSet.contains(testName)) {
      newSet.remove(testName);
    } else {
      newSet.add(testName);
    }
    state = newSet;

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsKey, jsonEncode(newSet.toList()));
    } catch (_) {
      // Ignore prefs error on web or test sandbox
    }
  }
}

final labFavouritesProvider =
    StateNotifierProvider<LabFavouritesNotifier, Set<String>>((ref) {
  return LabFavouritesNotifier(kDefaultFavourites);
});
