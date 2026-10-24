import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'settings_controller.dart';
import 'settings_model.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _baseUrlCtrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  final _newKeyCtrl = TextEditingController();
  final _newKeyLabelCtrl = TextEditingController();

  String _provider = 'groq';
  String _strategy = 'failover';
  bool _redactPii = true;
  bool _isInit = false;

  final Map<String, String> _presets = {
    'groq': 'https://api.groq.com/openai/v1',
    'openrouter': 'https://openrouter.ai/api/v1',
    'together': 'https://api.together.xyz/v1',
    'mistral': 'https://api.mistral.ai/v1',
    'openai': 'https://api.openai.com/v1',
    'ollama': 'http://localhost:11434/v1',
    'custom': '',
  };

  @override
  void dispose() {
    _baseUrlCtrl.dispose();
    _modelCtrl.dispose();
    _newKeyCtrl.dispose();
    _newKeyLabelCtrl.dispose();
    super.dispose();
  }

  void _syncWithSettings(AppSettings s) {
    if (_isInit) return;
    _isInit = true;
    _provider = s.llmProvider;
    _strategy = s.llmKeyStrategy;
    _baseUrlCtrl.text = s.llmBaseUrl;
    _modelCtrl.text = s.llmModel;
    _redactPii = s.privacyRedactPii;
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(settingsControllerProvider);
    final notifier = ref.read(settingsControllerProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings & Provider Configuration', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Reload',
            onPressed: () => notifier.loadAll(),
          ),
        ],
      ),
      body: state.settings.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 800),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.lock_person, size: 56, color: Colors.amber),
                  const SizedBox(height: 12),
                  Text(
                    'Unable to load settings. Please check your session and try again.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Your session credentials are managed securely by the application. '
                    'LLM provider keys belong in the LLM Key Pool section below.',
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
        data: (settings) {
          _syncWithSettings(settings);

          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildProviderSection(notifier, state.models),
                    const SizedBox(height: 24),
                    _buildKeyPoolSection(settings, notifier),
                    const SizedBox(height: 24),
                    _buildProbeSection(state, notifier),
                    const SizedBox(height: 24),
                    _buildUsageSection(state.usage),
                    const SizedBox(height: 40),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildProviderSection(SettingsController notifier, AsyncValue<List<String>> modelsAsync) {
    final models = modelsAsync.asData?.value ?? [];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('LLM Provider & Model Selection', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _presets.containsKey(_provider) ? _provider : 'custom',
              decoration: const InputDecoration(labelText: 'Provider Preset'),
              items: _presets.keys.map((p) {
                return DropdownMenuItem(value: p, child: Text(p.toUpperCase()));
              }).toList(),
              onChanged: (p) {
                if (p != null) {
                  setState(() {
                    _provider = p;
                    if (_presets[p]!.isNotEmpty) {
                      _baseUrlCtrl.text = _presets[p]!;
                    }
                  });
                }
              },
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _baseUrlCtrl,
              decoration: const InputDecoration(
                labelText: 'Base URL',
                prefixIcon: Icon(Icons.link),
              ),
            ),
            const SizedBox(height: 14),
            if (models.isNotEmpty) ...[
              DropdownButtonFormField<String>(
                initialValue: models.contains(_modelCtrl.text) ? _modelCtrl.text : null,
                decoration: const InputDecoration(labelText: 'Discovered Models'),
                items: models.map((m) => DropdownMenuItem(value: m, child: Text(m))).toList(),
                onChanged: (m) {
                  if (m != null) {
                    setState(() => _modelCtrl.text = m);
                  }
                },
              ),
              const SizedBox(height: 10),
            ],
            TextField(
              controller: _modelCtrl,
              decoration: const InputDecoration(
                labelText: 'Model ID (or custom)',
                prefixIcon: Icon(Icons.smart_toy),
                hintText: 'e.g. llama-3.3-70b-versatile, qwen-2.5-32b',
              ),
            ),
            const SizedBox(height: 14),
            SwitchListTile(
              title: const Text('Redact Personal Info (PII) before sending'),
              subtitle: const Text('Feasible name & ID masking to protect privacy'),
              value: _redactPii,
              onChanged: (v) => setState(() => _redactPii = v),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              icon: const Icon(Icons.save),
              label: const Text('Save Provider Settings'),
              onPressed: () async {
                final ok = await notifier.updateSettings({
                  'llm_provider': _provider,
                  'llm_base_url': _baseUrlCtrl.text,
                  'llm_model': _modelCtrl.text,
                  'privacy_redact_pii': _redactPii,
                  'llm_key_strategy': _strategy,
                });
                if (mounted) {
                  if (ok) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Provider settings saved successfully'), backgroundColor: Colors.green),
                    );
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Failed to save settings. Please check your session and try again.'), backgroundColor: Colors.red),
                    );
                  }
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildKeyPoolSection(AppSettings settings, SettingsController notifier) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                const Text('LLM Provider Key Pool & Rotation', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                DropdownButton<String>(
                  value: _strategy,
                  items: const [
                    DropdownMenuItem(value: 'failover', child: Text('Strategy: Failover')),
                    DropdownMenuItem(value: 'round_robin', child: Text('Strategy: Round Robin')),
                  ],
                  onChanged: (s) {
                    if (s != null) setState(() => _strategy = s);
                  },
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (settings.llmApiKeys.isEmpty)
              const Text('No LLM API keys configured yet. Add your Groq, Cerebras, or OpenAI key below.',
                  style: TextStyle(color: Colors.grey))
            else
              ...settings.llmApiKeys.map((k) {
                return ListTile(
                  dense: true,
                  leading: const Icon(Icons.vpn_key, color: Color(0xFF0D9488)),
                  title: Text(k.maskedKey, style: const TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text(k.label ?? 'default'),
                );
              }),
            const Divider(),
            const Text('Add New Provider Key', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  flex: 3,
                  child: TextField(
                    controller: _newKeyCtrl,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: 'LLM API Key (e.g. gsk_...)',
                      hintText: 'Paste Groq or OpenAI key',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: TextField(
                    controller: _newKeyLabelCtrl,
                    decoration: const InputDecoration(labelText: 'Label (e.g. groq-key-1)'),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () async {
                    final keyText = _newKeyCtrl.text.trim();
                    if (keyText.isNotEmpty) {
                      final labelText = _newKeyLabelCtrl.text.trim().isEmpty ? 'key' : _newKeyLabelCtrl.text.trim();
                      final ok = await notifier.updateSettings({
                        'llm_api_keys': [
                          {'key': keyText, 'label': labelText}
                        ],
                      });
                      if (mounted) {
                        if (ok) {
                          _newKeyCtrl.clear();
                          _newKeyLabelCtrl.clear();
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('LLM Key added to pool successfully!'), backgroundColor: Colors.green),
                          );
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Failed to add key. Please check your Server Access Key.'), backgroundColor: Colors.red),
                          );
                        }
                      }
                    }
                  },
                  child: const Text('Add Key'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProbeSection(SettingsState state, SettingsController notifier) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                const Text('Connection & Capabilities Probe', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ElevatedButton.icon(
                  icon: state.isTesting
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.network_check),
                  label: const Text('Test Connection'),
                  onPressed: state.isTesting ? null : () => notifier.testConnection(),
                ),
              ],
            ),
            const SizedBox(height: 12),
            state.testResult.when(
              loading: () => const Center(child: Padding(padding: EdgeInsets.all(8), child: CircularProgressIndicator())),
              error: (err, _) => Text('Test failed: $err', style: const TextStyle(color: Colors.red)),
              data: (result) {
                if (result == null) return const Text('Click "Test Connection" to run the capability ladder.');
                if (result.probes.isEmpty) return const Text('No keys available to probe.');

                return Column(
                  children: result.probes.map((p) {
                    final isOk = p.status == 'ok';
                    return Container(
                      margin: const EdgeInsets.symmetric(vertical: 4),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isOk ? const Color(0xFFF0FDF4) : const Color(0xFFFEF2F2),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: isOk ? Colors.green.shade200 : Colors.red.shade200),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(isOk ? Icons.check_circle : Icons.error, color: isOk ? Colors.green : Colors.red),
                              const SizedBox(width: 8),
                              Text('${p.label}: ${p.status.toUpperCase()}', style: const TextStyle(fontWeight: FontWeight.bold)),
                              const Spacer(),
                              Text('${p.latencyMs} ms', style: const TextStyle(color: Colors.grey)),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text('• Structured Mode: ${p.detectedStructuredMode}'),
                          Text('• Supports Tools: ${p.supportsTools ? "Yes" : "No"}'),
                          Text('• Reports Token Usage: ${p.hasUsage ? "Yes" : "No"}'),
                          if (p.hasReasoningTags) const Text('• Reasoning Tags: Detected (<think> will be stripped)'),
                          if (p.message != null) Text('• Detail: ${p.message}', style: const TextStyle(color: Colors.grey)),
                        ],
                      ),
                    );
                  }).toList(),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUsageSection(AsyncValue<UsageStats?> usageAsync) {
    final stats = usageAsync.asData?.value;
    if (stats == null) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Today\'s Usage & Quota Metrics', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildMetricCol('Tokens Used', '${stats.tokensToday}'),
                _buildMetricCol('LLM Calls', '${stats.callsToday}'),
                _buildMetricCol('Rate Limited Docs', '${stats.rateLimitedDocuments}', isAlert: stats.rateLimitedDocuments > 0),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCol(String title, String val, {bool isAlert = false}) {
    return Column(
      children: [
        Text(val, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: isAlert ? Colors.orange : const Color(0xFF0D9488))),
        const SizedBox(height: 4),
        Text(title, style: const TextStyle(fontSize: 12, color: Colors.grey)),
      ],
    );
  }
}
