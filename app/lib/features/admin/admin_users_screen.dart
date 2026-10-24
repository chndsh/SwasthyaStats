import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_controller.dart';
import 'admin_users_controller.dart';

class AdminUsersScreen extends ConsumerWidget {
  const AdminUsersScreen({super.key});

  Future<void> _create(BuildContext context, WidgetRef ref) async {
    final email = TextEditingController();
    final name = TextEditingController();
    final password = TextEditingController();
    final submitted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create user'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: email, decoration: const InputDecoration(labelText: 'Email')),
            TextField(controller: name, decoration: const InputDecoration(labelText: 'Display name')),
            TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Temporary password')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              final ok = await ref.read(adminUsersControllerProvider.notifier).create(
                    email: email.text,
                    password: password.text,
                    displayName: name.text,
                  );
              if (context.mounted) Navigator.pop(context, ok);
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
    email.dispose();
    name.dispose();
    password.dispose();
    if (submitted == true && context.mounted) {
      final temporary = ref.read(adminUsersControllerProvider).temporaryPassword;
      if (temporary != null) {
        await showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Temporary password'),
            content: SelectableText(temporary),
            actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Done'))],
          ),
        );
        ref.read(adminUsersControllerProvider.notifier).state =
            ref.read(adminUsersControllerProvider).copyWith(clearTemporaryPassword: true);
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentUserId = ref.watch(authControllerProvider).user?.id;
    final state = ref.watch(adminUsersControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Admin users')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _create(context, ref),
        child: const Icon(Icons.person_add),
      ),
      body: state.users.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Unable to load users: $error')),
        data: (users) => RefreshIndicator(
          onRefresh: ref.read(adminUsersControllerProvider.notifier).load,
          child: ListView(
            children: users
                .map(
                  (user) => ListTile(
                    title: Text(user.displayName?.isNotEmpty == true ? user.displayName! : user.email),
                    subtitle: Text(user.email),
                    trailing: user.id == currentUserId
                        ? const Text('You')
                        : IconButton(
                            tooltip: 'Delete user',
                            icon: const Icon(Icons.delete_outline),
                            onPressed: () async {
                              await ref.read(adminUsersControllerProvider.notifier).delete(user.id);
                            },
                          ),
                  ),
                )
                .toList(),
          ),
        ),
      ),
    );
  }
}
