import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'ask_controller.dart';
import 'ask_model.dart';
import '../../core/connectivity.dart';


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
          if (messages.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined),
              tooltip: 'Clear chat',
              onPressed: () {
                ref.read(askControllerProvider.notifier).clearHistory();
              },
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: messages.isEmpty
                ? const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.chat_bubble_outline, size: 48, color: Colors.grey),
                          SizedBox(height: 12),
                          Text(
                            'Ask anything about your health records',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                          SizedBox(height: 8),
                          Text(
                            'e.g. "What was my last HbA1c?" or "What medications am I taking?"\nAnswers include citation chips to verified records.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Colors.grey),
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
        if (isObs) {
          context.go('/labs');
        } else {
          context.go('/documents/${citation.id}');
        }
      },
    );
  }
}

