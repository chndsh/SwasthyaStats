import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'core/theme.dart';
import 'core/local_cache.dart';
import 'features/auth/auth_controller.dart';
import 'features/navigation/app_router.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
    ],
  );
  await container.read(authControllerProvider.notifier).initialize();
  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const SwasthyaStatsApp(),
    ),
  );
}

class SwasthyaStatsApp extends ConsumerWidget {
  const SwasthyaStatsApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = createAppRouter(ref);
    return MaterialApp.router(
      title: 'SwasthyaStats',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      routerConfig: router,
    );
  }
}
