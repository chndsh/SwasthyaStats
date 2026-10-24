import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';

class AdminScreen extends ConsumerStatefulWidget {
  const AdminScreen({super.key});

  @override
  ConsumerState<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends ConsumerState<AdminScreen> {
  late Future<List<dynamic>> users;
  final storage = const FlutterSecureStorage();

  @override
  void initState() {
    super.initState();
    users = _load();
  }

  Future<List<dynamic>> _load() async {
    final token = await storage.read(key: 'access_token');
    final response = await ref.read(apiClientProvider).auth.get(
      '/users',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data as List<dynamic>;
  }

  Future<void> _createUser() async {
    final email = TextEditingController();
    final password = TextEditingController();
    final displayName = TextEditingController();
    final created = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create user'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: email, decoration: const InputDecoration(labelText: 'Email')),
          TextField(controller: displayName, decoration: const InputDecoration(labelText: 'Display name')),
          TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () async {
            final token = await storage.read(key: 'access_token');
            await ref.read(apiClientProvider).auth.post('/users', data: {
              'email': email.text.trim(),
              'display_name': displayName.text.trim(),
              'password': password.text,
            }, options: Options(headers: {'Authorization': 'Bearer $token'}));
            if (context.mounted) Navigator.pop(context, true);
          }, child: const Text('Create')),
        ],
      ),
    );
    if (created == true && mounted) setState(() => users = _load());
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('User administration')),
        floatingActionButton: FloatingActionButton(
          onPressed: _createUser,
          child: const Icon(Icons.person_add),
        ),
        body: FutureBuilder<List<dynamic>>(
          future: users,
          builder: (context, snapshot) {
            if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
            return ListView(
              children: snapshot.data!.map((user) => ListTile(
                title: Text(user['display_name'] ?? user['email']),
                subtitle: Text(user['email']),
              )).toList(),
            );
          },
        ),
      );
}
