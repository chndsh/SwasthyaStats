import 'package:flutter_test/flutter_test.dart';
import 'package:app/features/auth/token_storage.dart';

class _MemoryTokenStorage implements TokenStorage {
  String? accessToken;
  String? refreshToken;

  @override
  Future<String?> readAccessToken() async => accessToken;

  @override
  Future<String?> readRefreshToken() async => refreshToken;

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  @override
  Future<void> clear() async {
    accessToken = null;
    refreshToken = null;
  }

  @override
  Future<bool> hasCompleteSession() async {
    final access = await readAccessToken();
    final refresh = await readRefreshToken();
    return access != null &&
        access.isNotEmpty &&
        refresh != null &&
        refresh.isNotEmpty;
  }
}

void main() {
  test('writes and reads a complete session', () async {
    final storage = _MemoryTokenStorage();

    await storage.writeTokens(accessToken: 'access-1', refreshToken: 'refresh-1');

    expect(await storage.readAccessToken(), 'access-1');
    expect(await storage.readRefreshToken(), 'refresh-1');
    expect(await storage.hasCompleteSession(), isTrue);
  });

  test('replaces rotated tokens', () async {
    final storage = _MemoryTokenStorage();
    await storage.writeTokens(accessToken: 'access-1', refreshToken: 'refresh-1');

    await storage.writeTokens(accessToken: 'access-2', refreshToken: 'refresh-2');

    expect(await storage.readAccessToken(), 'access-2');
    expect(await storage.readRefreshToken(), 'refresh-2');
  });

  test('clear removes both tokens', () async {
    final storage = _MemoryTokenStorage();
    await storage.writeTokens(accessToken: 'access', refreshToken: 'refresh');

    await storage.clear();

    expect(await storage.hasCompleteSession(), isFalse);
  });

  test('an incomplete session is not considered authenticated', () async {
    final storage = _MemoryTokenStorage();
    await storage.writeTokens(accessToken: 'access', refreshToken: '');

    expect(await storage.hasCompleteSession(), isFalse);
  });
}
