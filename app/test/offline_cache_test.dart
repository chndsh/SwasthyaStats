import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:app/core/local_cache.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('LocalCacheService saves and retrieves documents and labs', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final cache = LocalCacheService(prefs);

    await cache.cacheDocuments([
      {'id': 1, 'filename': 'test.pdf', 'status': 'confirmed'}
    ]);
    final docs = await cache.getCachedDocuments();
    expect(docs.length, 1);
    expect(docs.first['filename'], 'test.pdf');

    await cache.cacheLabs([
      {'test_name': 'Hemoglobin', 'count': 2, 'latest_value': 14.2}
    ]);
    final labs = await cache.getCachedLabs();
    expect(labs.length, 1);
    expect(labs.first['test_name'], 'Hemoglobin');
  });
}
