import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const accessTokenKey = 'access_token';
const refreshTokenKey = 'refresh_token';

abstract class TokenStorage {
  Future<String?> readAccessToken();
  Future<String?> readRefreshToken();
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  });
  Future<void> clear();

  Future<bool> hasCompleteSession();
}

class SecureTokenStorage implements TokenStorage {
  final FlutterSecureStorage _storage;

  SecureTokenStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  @override
  Future<String?> readAccessToken() => _storage.read(key: accessTokenKey);

  @override
  Future<String?> readRefreshToken() => _storage.read(key: refreshTokenKey);

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: accessTokenKey, value: accessToken);
    await _storage.write(key: refreshTokenKey, value: refreshToken);
  }

  @override
  Future<void> clear() async {
    await Future.wait([
      _storage.delete(key: accessTokenKey),
      _storage.delete(key: refreshTokenKey),
    ]);
  }

  @override
  Future<bool> hasCompleteSession() async {
    final accessToken = await readAccessToken();
    final refreshToken = await readRefreshToken();
    return accessToken != null &&
        accessToken.isNotEmpty &&
        refreshToken != null &&
        refreshToken.isNotEmpty;
  }
}

final tokenStorageProvider = Provider<TokenStorage>((ref) {
  return SecureTokenStorage();
});
