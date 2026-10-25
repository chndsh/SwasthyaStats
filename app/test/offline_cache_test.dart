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

  test('LocalCacheService isolates cache per user', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final user1Cache = LocalCacheService(prefs, userId: 1);
    final user2Cache = LocalCacheService(prefs, userId: 2);

    await user1Cache.cacheLabs([
      {'test_name': 'Hemoglobin', 'count': 1}
    ]);
    await user1Cache.cacheAskHistory([
      {'role': 'user', 'text': 'User 1 private question'}
    ]);

    expect(await user2Cache.getCachedLabs(), isEmpty);
    expect(await user2Cache.getCachedAskHistory(), isEmpty);

    await user2Cache.cacheLabs([
      {'test_name': 'WBC', 'count': 5}
    ]);
    await user2Cache.cacheAskHistory([
      {'role': 'user', 'text': 'User 2 question'}
    ]);

    final u1Labs = await user1Cache.getCachedLabs();
    final u2Labs = await user2Cache.getCachedLabs();
    expect(u1Labs.first['test_name'], 'Hemoglobin');
    expect(u2Labs.first['test_name'], 'WBC');

    final u1Ask = await user1Cache.getCachedAskHistory();
    final u2Ask = await user2Cache.getCachedAskHistory();
    expect(u1Ask.first['text'], 'User 1 private question');
    expect(u2Ask.first['text'], 'User 2 question');
  });
}
