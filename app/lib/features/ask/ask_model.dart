class CitationRef {
  final String type; // 'obs' | 'doc'
  final int id;
  final int? page;

  CitationRef({
    required this.type,
    required this.id,
    this.page,
  });

  factory CitationRef.fromJson(Map<String, dynamic> json) {
    return CitationRef(
      type: json['type'] as String? ?? 'obs',
      id: json['id'] as int? ?? 0,
      page: json['page'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'id': id,
        if (page != null) 'page': page,
      };
}

class AskMessage {
  final String role; // 'user' | 'assistant'
  final String text;
  final List<CitationRef> citations;
  final DateTime timestamp;

  AskMessage({
    required this.role,
    required this.text,
    this.citations = const [],
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  factory AskMessage.fromJson(Map<String, dynamic> json) {
    final rawCitations = (json['citations'] as List<dynamic>?) ?? [];
    return AskMessage(
      role: json['role'] as String? ?? 'user',
      text: json['text'] as String? ?? '',
      citations: rawCitations
          .map((c) => CitationRef.fromJson(c as Map<String, dynamic>))
          .toList(),
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'] as String) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
        'role': role,
        'text': text,
        'citations': citations.map((c) => c.toJson()).toList(),
        'timestamp': timestamp.toIso8601String(),
      };
}
