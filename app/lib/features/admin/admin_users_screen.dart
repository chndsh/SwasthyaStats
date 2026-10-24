import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'dart:math';

import '../auth/auth_controller.dart';
import 'admin_users_controller.dart';

class AdminUsersScreen extends ConsumerWidget {
  const AdminUsersScreen({super.key});

  String _temporaryPassword() {
    const alphabet =
        'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#';
    final random = Random.secure();
    return List.generate(
      14,
      (_) => alphabet[random.nextInt(alphabet.length)],
    ).join();
  }

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
            TextField(
              controller: email,
              decoration: const InputDecoration(labelText: 'Email'),
            ),
            TextField(
              controller: name,
              decoration: const InputDecoration(labelText: 'Display name'),
            ),
            TextField(
              controller: password,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Temporary password',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              final ok = await ref
                  .read(adminUsersControllerProvider.notifier)
                  .create(
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
      final temporary = ref
          .read(adminUsersControllerProvider)
          .temporaryPassword;
      if (temporary != null) {
        await showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Temporary password'),
            content: SelectableText(temporary),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Done'),
              ),
            ],
          ),
        );
        ref
            .read(adminUsersControllerProvider.notifier)
            .clearTemporaryPassword();
      }
    }
  }

  Future<void> _reset(BuildContext context, WidgetRef ref, int userId) async {
    final password = _temporaryPassword();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset password?'),
        content: const Text(
          'This invalidates the user\'s existing refresh tokens and requires a new password on next sign-in.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Reset'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    final ok = await ref
        .read(adminUsersControllerProvider.notifier)
        .reset(userId, password);
    if (!ok || !context.mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Temporary password'),
        content: SelectableText(password),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Done'),
          ),
        ],
      ),
    );
    ref.read(adminUsersControllerProvider.notifier).clearTemporaryPassword();
  }

  Future<void> _delete(
    BuildContext context,
    WidgetRef ref,
    int userId,
    String email,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete user?'),
        content: Text('Delete $email and all of this user\'s health data?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      await ref.read(adminUsersControllerProvider.notifier).delete(userId);
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
        error: (error, _) =>
            Center(child: Text('Unable to load users: $error')),
        data: (users) => RefreshIndicator(
          onRefresh: ref.read(adminUsersControllerProvider.notifier).load,
          child: ListView(
            children: users
                .map(
                  (user) => ListTile(
                    title: Text(
                      user.displayName?.isNotEmpty == true
                          ? user.displayName!
                          : user.email,
                    ),
                    subtitle: Text(user.email),
                    trailing: user.id == currentUserId
                        ? const Text('You')
                        : Wrap(
                            spacing: 4,
                            children: [
                              IconButton(
                                tooltip: 'Reset password',
                                icon: const Icon(Icons.key),
                                onPressed: () => _reset(context, ref, user.id),
                              ),
                              IconButton(
                                tooltip: 'Delete user',
                                icon: const Icon(Icons.delete_outline),
                                onPressed: () =>
                                    _delete(context, ref, user.id, user.email),
                              ),
                            ],
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
