import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app/core/api_client.dart';
import 'package:app/features/admin/admin_users_controller.dart';
import 'package:app/features/auth/token_storage.dart';

class _Storage implements TokenStorage {
  @override
  Future<String?> readAccessToken() async => 'access';

  @override
  Future<String?> readRefreshToken() async => 'refresh';

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {}

  @override
  Future<void> clear() async {}

  @override
  Future<bool> hasCompleteSession() async => true;
}

class _Adapter implements HttpClientAdapter {
  final List<String> paths = [];
  final List<String> methods = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    paths.add(options.uri.path);
    methods.add(options.method);
    final path = options.uri.path;
    if (path.endsWith('/auth/users') && options.method == 'GET') {
      return ResponseBody.fromString(
        '[{"id":1,"email":"user@example.com","display_name":"User","is_admin":false,"must_change_password":true}]',
        200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    if (path.endsWith('/auth/users') && options.method == 'POST') {
      return ResponseBody.fromString(
        '{"id":2,"email":"new@example.com","display_name":"New","is_admin":false,"must_change_password":true}',
        201,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    return ResponseBody.fromString('{}', 204);
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('admin user operations use the root auth client paths', () async {
    final storage = _Storage();
    final client = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      storage: storage,
    );
    final adapter = _Adapter();
    client.dio.httpClientAdapter = adapter;
    client.authDio.httpClientAdapter = adapter;
    final controller = AdminUsersController(client);
    await Future<void>.delayed(Duration.zero);
    await controller.create(
      email: 'new@example.com',
      password: 'temporary123',
      displayName: 'New',
    );
    await controller.reset(1, 'resetpassword');
    await controller.delete(1);

    expect(adapter.paths, everyElement(contains('/auth/users')));
    expect(adapter.paths, isNot(contains('/api/v1/auth/users')));
    expect(
      adapter.methods,
      containsAll(<String>['GET', 'POST', 'PUT', 'DELETE']),
    );
  });
}
