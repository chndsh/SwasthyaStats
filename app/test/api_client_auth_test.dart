import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app/core/api_client.dart';
import 'package:app/features/auth/token_storage.dart';

class _MemoryStorage implements TokenStorage {
  String? access;
  String? refresh;

  @override
  Future<String?> readAccessToken() async => access;

  @override
  Future<String?> readRefreshToken() async => refresh;

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    access = accessToken;
    refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    access = null;
    refresh = null;
  }

  @override
  Future<bool> hasCompleteSession() async =>
      access?.isNotEmpty == true && refresh?.isNotEmpty == true;
}

class _Adapter implements HttpClientAdapter {
  final bool refreshSucceeds;
  final List<Map<String, dynamic>> requests = [];
  int protectedCalls = 0;

  _Adapter({this.refreshSucceeds = true});

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add({
      'path': options.uri.path,
      'authorization': options.headers['Authorization'],
      'hasLegacyApiKey': options.headers.containsKey('X-API-Key'),
    });
    final path = options.uri.path;
    if (path.endsWith('/auth/refresh')) {
      if (!refreshSucceeds) {
        return ResponseBody.fromString('{"detail":"revoked"}', 401);
      }
      return ResponseBody.fromString(
        '{"access_token":"new-access","refresh_token":"new-refresh"}',
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    if (path.endsWith('/documents')) {
      protectedCalls++;
      if (protectedCalls == 1) {
        return ResponseBody.fromString('{"detail":"expired"}', 401);
      }
      return ResponseBody.fromString(
        '{"items":[]}',
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    return ResponseBody.fromString('{}', 200);
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('adds bearer authentication and retries after one refresh', () async {
    final storage = _MemoryStorage()
      ..access = 'old-access'
      ..refresh = 'old-refresh';
    final adapter = _Adapter();
    final client = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      storage: storage,
    );
    client.dio.httpClientAdapter = adapter;
    client.authDio.httpClientAdapter = adapter;

    final response = await client.dio.get('/documents');

    expect(response.statusCode, 200);
    expect(storage.access, 'new-access');
    expect(storage.refresh, 'new-refresh');
    expect(adapter.protectedCalls, 2);
    expect(adapter.requests[0]['authorization'], 'Bearer old-access');
    expect(adapter.requests[0]['hasLegacyApiKey'], isFalse);
    expect(adapter.requests[2]['authorization'], 'Bearer new-access');
  });

  test('failed refresh clears credentials and reports expiration', () async {
    final storage = _MemoryStorage()
      ..access = 'old-access'
      ..refresh = 'old-refresh';
    final adapter = _Adapter(refreshSucceeds: false);
    var expired = false;
    final client = ApiClient(storage: storage)
      ..onSessionExpired = () async => expired = true;
    client.dio.httpClientAdapter = adapter;
    client.authDio.httpClientAdapter = adapter;

    await expectLater(client.dio.get('/documents'), throwsA(isA<DioException>()));

    expect(await storage.hasCompleteSession(), isFalse);
    expect(expired, isTrue);
    expect(adapter.protectedCalls, 1);
  });
}
