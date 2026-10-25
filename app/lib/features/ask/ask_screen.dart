import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'ask_controller.dart';
import 'ask_model.dart';
import '../../core/connectivity.dart';
import '../navigation/user_menu_button.dart';


class AskScreen extends ConsumerStatefulWidget {
  const AskScreen({super.key});

  @override
  ConsumerState<AskScreen> createState() => _AskScreenState();
}

class _AskScreenState extends ConsumerState<AskScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _isLoading = false;

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSend() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isLoading) return;

    _textController.clear();
    setState(() => _isLoading = true);
    _scrollToBottom();

    try {
      await ref.read(askControllerProvider.notifier).sendQuestion(text);
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
        _scrollToBottom();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isOffline = ref.watch(isOfflineProvider);
    final messagesAsync = ref.watch(askControllerProvider);
    final messages = messagesAsync.value ?? [];

    if (isOffline) {
      return Scaffold(
        appBar: AppBar(title: const Text('Ask Health Records')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.wifi_off, size: 48, color: Colors.grey),
                SizedBox(height: 16),
                Text(
                  "You're offline",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                SizedBox(height: 8),
                Text(
                  'Connect to the internet to query health records.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey),
                ),
              ],
            ),
          ),
        ),
      );
    }


    return Scaffold(
      appBar: AppBar(
        title: const Text('Ask Health Records'),
        actions: [
          IconButton(
            icon: const Icon(Icons.restart_alt),
            tooltip: 'Clear conversation history',
            onPressed: () async {
              final confirmed = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Reset conversation?'),
                  content: const Text(
                    'This will clear the current chat messages and conversation history.',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx, false),
                      child: const Text('Cancel'),
                    ),
                    FilledButton(
                      onPressed: () => Navigator.pop(ctx, true),
                      child: const Text('Reset'),
                    ),
                  ],
                ),
              );
              if (confirmed == true) {
                await ref.read(askControllerProvider.notifier).clearHistory();
              }
            },
          ),
          const UserMenuButton(),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: messages.isEmpty
                ? Center(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.chat_bubble_outline, size: 48, color: Colors.grey),
                          const SizedBox(height: 12),
                          const Text(
                            'Ask anything about your health records',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'Answers include citation chips to verified records.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Colors.grey),
                          ),
                          const SizedBox(height: 24),
                          const Text(
                            'Suggested questions:',
                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.grey),
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            alignment: WrapAlignment.center,
                            children: [
                              'What was my last HbA1c?',
                              'Are any results abnormal?',
                              'What should I ask my doctor about my results?',
                              'Show my lipid profile trends',
                              'List all my recorded blood tests',
                            ]
                                .map(
                                  (q) => ActionChip(
                                    label: Text(q, style: const TextStyle(fontSize: 12)),
                                    onPressed: () {
                                      _textController.text = q;
                                      _handleSend();
                                    },
                                  ),
                                )
                                .toList(),
                          ),
                        ],
                      ),
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    itemCount: messages.length + (_isLoading ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == messages.length && _isLoading) {
                        return const Align(
                          alignment: Alignment.centerLeft,
                          child: Padding(
                            padding: EdgeInsets.symmetric(vertical: 8),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                SizedBox(
                                  width: 16,
                                  height: 16,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                ),
                                SizedBox(width: 8),
                                Text('Consulting records...', style: TextStyle(color: Colors.grey)),
                              ],
                            ),
                          ),
                        );
                      }
                      final msg = messages[index];
                      return _MessageBubble(message: msg);
                    },
                  ),
          ),
          Container(
            padding: const EdgeInsets.all(8.0),
            decoration: BoxDecoration(
              color: Theme.of(context).cardColor,
              border: Border(top: BorderSide(color: Theme.of(context).dividerColor)),
            ),
            child: SafeArea(
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      decoration: const InputDecoration(
                        hintText: 'Ask a question...',
                        border: InputBorder.none,
                        contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                      onSubmitted: (_) => _handleSend(),
                    ),
                  ),
                  IconButton(
                    icon: _isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.send, color: Color(0xFF0D9488)),
                    onPressed: _isLoading ? null : _handleSend,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final AskMessage message;

  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final align = isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;
    final bg = isUser ? const Color(0xFF0D9488) : Theme.of(context).colorScheme.surfaceContainerHighest;

    final textStyle = TextStyle(
      color: isUser ? Colors.white : Theme.of(context).textTheme.bodyMedium?.color,
    );

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Column(
        crossAxisAlignment: align,
        children: [
          Container(
            constraints: const BoxConstraints(maxWidth: 600),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(16),
            ),
            child: isUser
                ? SelectableText(message.text, style: textStyle)
                : _AssistantAnswerView(text: message.text, citations: message.citations),
          ),
        ],
      ),
    );
  }
}

class _AssistantAnswerView extends StatelessWidget {
  final String text;
  final List<CitationRef> citations;

  const _AssistantAnswerView({required this.text, required this.citations});

  // Strip inline [obs:N] / [doc:N p:N] tags — citations are shown as chips below
  static final _citationTag = RegExp(r'\s*\[(?:obs|doc):\d+(?:\s+p:\d+)?\]');

  @override
  Widget build(BuildContext context) {
    final cleanText = text.replaceAll(_citationTag, '').trim();
    final bodyColor = Theme.of(context).textTheme.bodyMedium?.color;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        MarkdownBody(
          data: cleanText,
          selectable: true,
          styleSheet: MarkdownStyleSheet(
            p: TextStyle(color: bodyColor, fontSize: 14, height: 1.5),
            strong: TextStyle(color: bodyColor, fontWeight: FontWeight.bold, fontSize: 14),
            em: TextStyle(color: bodyColor, fontStyle: FontStyle.italic, fontSize: 14),
            code: TextStyle(
              color: bodyColor,
              backgroundColor: Colors.black12,
              fontFamily: 'monospace',
              fontSize: 13,
            ),
            listBullet: TextStyle(color: bodyColor, fontSize: 14),
          ),
        ),
        if (citations.isNotEmpty) ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: citations.map((c) => _CitationChip(citation: c)).toList(),
          ),
        ],
      ],
    );
  }
}

class _CitationChip extends StatelessWidget {
  final CitationRef citation;
  const _CitationChip({required this.citation});

  @override
  Widget build(BuildContext context) {
    final isObs = citation.type == 'obs';
    final label = isObs ? 'obs:${citation.id}' : 'doc:${citation.id}${citation.page != null ? ' p:${citation.page}' : ''}';

    return ActionChip(
      visualDensity: VisualDensity.compact,
      padding: EdgeInsets.zero,
      labelPadding: const EdgeInsets.symmetric(horizontal: 6),
      avatar: Icon(isObs ? Icons.bookmark_border : Icons.description, size: 14),
      label: Text(label, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
      onPressed: () {
        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          builder: (ctx) => _CitationBottomSheet(citation: citation),
        );
      },
    );
  }
}

class _CitationBottomSheet extends StatelessWidget {
  final CitationRef citation;

  const _CitationBottomSheet({required this.citation});

  @override
  Widget build(BuildContext context) {
    final isObs = citation.type == 'obs';

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: const Color(0xFFE6FFFA),
                  child: Icon(
                    isObs ? Icons.bookmark_border : Icons.description,
                    color: const Color(0xFF0D9488),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isObs ? 'Cited Observation Record' : 'Cited Document Page',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                      ),
                      Text(
                        isObs
                            ? 'Record ID: #${citation.id}'
                            : 'Document ID: #${citation.id}${citation.page != null ? ' (Page ${citation.page})' : ''}',
                        style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const Divider(height: 24),
            Text(
              isObs
                  ? 'This fact in the AI answer was cited directly from confirmed observation record #${citation.id}. You can inspect its trend chart and historical values in Labs.'
                  : 'This fact in the AI answer was cited directly from document #${citation.id}${citation.page != null ? ' (Page ${citation.page})' : ''}.',
              style: TextStyle(fontSize: 14, color: Colors.grey.shade800, height: 1.4),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFF0D9488),
                    ),
                    icon: Icon(isObs ? Icons.insights : Icons.visibility, size: 18),
                    label: Text(isObs ? 'View in Labs' : 'Open Document'),
                    onPressed: () {
                      Navigator.pop(context);
                      if (isObs) {
                        context.go('/labs');
                      } else {
                        context.go('/documents/${citation.id}');
                      }
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}


