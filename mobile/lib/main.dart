import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const ProviderScope(child: SmartDoorApp()));
}

class SmartDoorApp extends StatelessWidget {
  const SmartDoorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sentinel Home',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.dark,
      darkTheme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF09090B),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFAFAFA),
          secondary: Color(0xFF10B981),
          surface: Color(0xFF111114),
        ),
        cardTheme: CardTheme(
          color: const Color(0xFF111114),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: BorderSide(color: Colors.white.withOpacity(0.08)),
          ),
        ),
      ),
      home: const SmartDoorHome(),
    );
  }
}

class DoorEvent {
  final String id;
  final String timestamp;
  final String personLabel;
  final String caption;
  final String? imageUrl;

  DoorEvent({
    required this.id,
    required this.timestamp,
    required this.personLabel,
    required this.caption,
    this.imageUrl,
  });

  factory DoorEvent.fromJson(Map<String, dynamic> json, String baseUrl) {
    final id = (json['id'] ?? '').toString();
    return DoorEvent(
      id: id,
      timestamp: (json['timestamp'] ?? '').toString(),
      personLabel: (json['personLabel'] ?? 'unknown').toString(),
      caption: (json['caption'] ?? 'Activity detected at front entrance').toString(),
      imageUrl: id.isNotEmpty ? '$baseUrl/api/events/$id/image' : null,
    );
  }
}

class SmartDoorHome extends StatefulWidget {
  const SmartDoorHome({super.key});

  @override
  State<SmartDoorHome> createState() => _SmartDoorHomeState();
}

class _SmartDoorHomeState extends State<SmartDoorHome> {
  int _tabIndex = 0;
  String backendUrl = 'http://172.16.19.206:8085';

  bool isConnected = false;
  bool doorUnlocked = false;
  int unlockRemaining = 0;
  bool alarmActive = false;
  String currentPerson = 'none';
  Uint8List? liveFrameBytes;

  List<DoorEvent> events = [
    DoorEvent(
      id: "demo-1",
      timestamp: "14:20:15",
      personLabel: "courier",
      caption: "Package delivered at front door by postal carrier",
    ),
    DoorEvent(
      id: "demo-2",
      timestamp: "13:45:00",
      personLabel: "Alice",
      caption: "Alice arrived home and door unlocked",
    ),
  ];

  List<String> knownPeople = [];
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _initConnection();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _initConnection() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString('backend_url');
      if (saved != null && saved.isNotEmpty && mounted) {
        setState(() => backendUrl = saved);
      }
    } catch (_) {}

    await _refreshAll();
    _pollTimer = Timer.periodic(const Duration(milliseconds: 650), (_) {
      if (!mounted) return;
      if (_tabIndex == 0) {
        _fetchLiveFrame();
        _fetchDoorStatus();
      }
    });
  }

  Future<void> _refreshAll() async {
    await Future.wait([
      _fetchDoorStatus(),
      _fetchLiveFrame(),
      _fetchEvents(),
      _fetchPeople(),
    ]);
  }

  Future<void> _fetchLiveFrame() async {
    try {
      final res = await http
          .get(Uri.parse('$backendUrl/api/camera/frame?t=${DateTime.now().millisecondsSinceEpoch}'))
          .timeout(const Duration(seconds: 2));
      if (res.statusCode == 200 && res.bodyBytes.isNotEmpty && mounted) {
        setState(() {
          liveFrameBytes = res.bodyBytes;
          isConnected = true;
        });
      }
    } catch (_) {}
  }

  Future<void> _fetchDoorStatus() async {
    try {
      final res = await http
          .get(Uri.parse('$backendUrl/api/door/status'))
          .timeout(const Duration(seconds: 2));
      if (res.statusCode == 200 && mounted) {
        final d = jsonDecode(res.body);
        setState(() {
          isConnected = true;
          doorUnlocked = d['unlocked'] == true;
          unlockRemaining = (d['unlockRemainingSeconds'] ?? 0) as int;
          alarmActive = d['alarmActive'] == true;
          currentPerson = (d['currentPerson'] ?? 'none').toString();
        });
      }
    } catch (_) {
      if (mounted) setState(() => isConnected = false);
    }
  }

  Future<void> _fetchEvents() async {
    try {
      final res = await http
          .get(Uri.parse('$backendUrl/api/events'))
          .timeout(const Duration(seconds: 3));
      if (res.statusCode == 200 && mounted) {
        final body = jsonDecode(res.body);
        final List raw = body is Map && body['content'] is List
            ? body['content']
            : (body is List ? body : []);
        if (raw.isNotEmpty) {
          setState(() {
            events = raw
                .map((e) => DoorEvent.fromJson(e as Map<String, dynamic>, backendUrl))
                .toList();
          });
        }
      }
    } catch (_) {}
  }

  Future<void> _fetchPeople() async {
    try {
      final res = await http
          .get(Uri.parse('$backendUrl/api/people'))
          .timeout(const Duration(seconds: 3));
      if (res.statusCode == 200 && mounted) {
        final List raw = jsonDecode(res.body);
        setState(() {
          knownPeople = raw.map((e) => e['name'].toString()).toList();
        });
      }
    } catch (_) {}
  }

  Future<void> _sendDoorAction(String action) async {
    try {
      final res = await http
          .post(Uri.parse('$backendUrl/api/door/$action'))
          .timeout(const Duration(seconds: 3));
      if (res.statusCode == 200 && mounted) {
        await _fetchDoorStatus();
        await _fetchEvents();
        final msg = action == 'unlock'
            ? 'Porte ouverte pour 10 secondes.'
            : (action == 'lock' ? 'Porte verrouillee.' : 'Alarme declenchee.');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg), backgroundColor: action == 'alarm' ? Colors.redAccent : const Color(0xFF10B981)),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Serveur PC injoignable (verifiez Wi-Fi et IP).'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  Future<void> _enrollCurrentPersonDialog() async {
    final nameCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Enregistrer la personne devant la camera'),
        content: TextField(
          controller: nameCtrl,
          decoration: const InputDecoration(
            labelText: 'Prenom / Nom (ex: Yassine)',
            hintText: 'Regardez la camera du PC',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          ElevatedButton(
            onPressed: () async {
              final name = nameCtrl.text.trim();
              if (name.isEmpty) return;
              Navigator.pop(ctx);
              try {
                final res = await http.post(
                  Uri.parse('$backendUrl/api/people/enroll-live'),
                  body: {'name': name},
                ).timeout(const Duration(seconds: 5));
                if (mounted) {
                  if (res.statusCode == 200) {
                    _fetchPeople();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('$name enregistre(e). Ouverture auto active.'), backgroundColor: const Color(0xFF10B981)),
                    );
                  } else {
                    final err = jsonDecode(res.body)['detail'] ?? 'Visage non detecte';
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(err.toString()), backgroundColor: Colors.amber),
                    );
                  }
                }
              } catch (_) {}
            },
            child: const Text('Enregistrer'),
          ),
        ],
      ),
    );
  }

  Future<void> _deletePerson(String name) async {
    try {
      await http.delete(Uri.parse('$backendUrl/api/people/${Uri.encodeComponent(name)}'));
      _fetchPeople();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF111114),
        surfaceTintColor: Colors.transparent,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Smart Door Live Feed', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            Text(
              isConnected ? 'Connecte • $backendUrl' : 'Hors-ligne • $backendUrl',
              style: TextStyle(fontSize: 11, color: isConnected ? const Color(0xFF10B981) : Colors.amber),
            ),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh, size: 20), onPressed: _refreshAll),
          IconButton(icon: const Icon(Icons.settings_outlined, size: 20), onPressed: _showSettingsDialog),
        ],
      ),
      body: IndexedStack(
        index: _tabIndex,
        children: [
          _buildLiveCameraTab(),
          _buildEventsTab(),
          _buildPeopleTab(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tabIndex,
        backgroundColor: const Color(0xFF111114),
        indicatorColor: Colors.white.withOpacity(0.1),
        onDestinationSelected: (i) {
          setState(() => _tabIndex = i);
          if (i == 1) _fetchEvents();
          if (i == 2) _fetchPeople();
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.videocam_outlined), selectedIcon: Icon(Icons.videocam), label: 'Camera'),
          NavigationDestination(icon: Icon(Icons.history), label: 'Historique'),
          NavigationDestination(icon: Icon(Icons.people_outline), selectedIcon: Icon(Icons.people), label: 'Personnes'),
        ],
      ),
    );
  }

  Widget _buildLiveCameraTab() {
    final isUnknown = currentPerson == 'unknown';
    final isKnown = currentPerson != 'none' && !isUnknown;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(14),
          child: Container(
            height: 240,
            color: const Color(0xFF050507),
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (liveFrameBytes != null)
                  Image.memory(liveFrameBytes!, fit: BoxFit.cover, gaplessPlayback: true)
                else
                  const Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.videocam_off_outlined, size: 42, color: Colors.white30),
                        SizedBox(height: 8),
                        Text('En attente du flux camera PC...', style: TextStyle(color: Colors.white54, fontSize: 13)),
                      ],
                    ),
                  ),
                Positioned(
                  top: 10,
                  left: 10,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xCC09090B),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.white12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.circle, size: 8, color: isConnected ? Colors.redAccent : Colors.grey),
                        const SizedBox(width: 6),
                        const Text('LIVE CAM PC', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 14),
        Card(
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: isKnown ? const Color(0xFF10B981) : (isUnknown ? Colors.redAccent : const Color(0xFF27272A)),
              child: Icon(
                isKnown ? Icons.verified_user_outlined : (isUnknown ? Icons.warning_amber_rounded : Icons.sensor_door_outlined),
                color: isKnown || isUnknown ? Colors.black : Colors.white70,
                size: 20,
              ),
            ),
            title: Text(
              isKnown
                  ? 'Devant la porte : $currentPerson (Autorise)'
                  : (isUnknown ? 'Devant la porte : VISITEUR INCONNU' : 'Entree degagee'),
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5),
            ),
            subtitle: Text(
              doorUnlocked ? 'Porte OUVERTE (${unlockRemaining}s)' : 'Porte VERROUILLEE',
              style: TextStyle(fontSize: 12, color: doorUnlocked ? const Color(0xFF10B981) : Colors.white60),
            ),
          ),
        ),
        const SizedBox(height: 14),
        SizedBox(
          height: 54,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: doorUnlocked ? const Color(0xFF10B981) : const Color(0xFFFAFAFA),
              foregroundColor: const Color(0xFF09090B),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            icon: Icon(doorUnlocked ? Icons.lock_open : Icons.door_front_door_outlined, size: 22),
            label: Text(
              doorUnlocked ? 'PORTE OUVERTE (${unlockRemaining}s)' : 'OUVRIR LA PORTE (10s)',
              style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700),
            ),
            onPressed: () => _sendDoorAction('unlock'),
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white12),
                  padding: const EdgeInsets.symmetric(vertical: 13),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                icon: const Icon(Icons.lock_outline, size: 18),
                label: const Text('Verrouiller'),
                onPressed: () => _sendDoorAction('lock'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.redAccent,
                  side: BorderSide(color: Colors.redAccent.withOpacity(0.45)),
                  padding: const EdgeInsets.symmetric(vertical: 13),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                icon: const Icon(Icons.notifications_active_outlined, size: 18),
                label: const Text('Alarme'),
                onPressed: () => _sendDoorAction('alarm'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white70,
            side: const BorderSide(color: Colors.white12),
            padding: const EdgeInsets.symmetric(vertical: 12),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
          icon: const Icon(Icons.person_add_alt_1_outlined, size: 18),
          label: const Text('Enregistrer la personne devant la camera'),
          onPressed: _enrollCurrentPersonDialog,
        ),
      ],
    );
  }

  Widget _buildEventsTab() {
    return RefreshIndicator(
      onRefresh: _fetchEvents,
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: events.length,
        itemBuilder: (context, index) {
          final event = events[index];
          final isAlert = event.personLabel.toLowerCase() == 'unknown';
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => EventDetailScreen(event: event)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (event.imageUrl != null && isConnected)
                    SizedBox(
                      height: 150,
                      width: double.infinity,
                      child: Image.network(
                        event.imageUrl!,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                      ),
                    ),
                  ListTile(
                    leading: CircleAvatar(
                      backgroundColor: isAlert ? Colors.redAccent.withOpacity(0.2) : const Color(0xFF10B981).withOpacity(0.2),
                      child: Icon(
                        isAlert ? Icons.warning_amber_rounded : Icons.check_circle_outline,
                        color: isAlert ? Colors.redAccent : const Color(0xFF10B981),
                        size: 20,
                      ),
                    ),
                    title: Text(event.caption, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5)),
                    subtitle: Text('${event.personLabel} • ${event.timestamp}', style: const TextStyle(fontSize: 11.5)),
                    trailing: const Icon(Icons.chevron_right, size: 18),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildPeopleTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ElevatedButton.icon(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFFFAFAFA),
            foregroundColor: const Color(0xFF09090B),
            padding: const EdgeInsets.symmetric(vertical: 13),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
          icon: const Icon(Icons.person_add_outlined, size: 19),
          label: const Text('Ajouter depuis la camera du PC', style: TextStyle(fontWeight: FontWeight.w700)),
          onPressed: _enrollCurrentPersonDialog,
        ),
        const SizedBox(height: 16),
        Text('Personnes autorisees (${knownPeople.length})',
            style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: Colors.white60)),
        const SizedBox(height: 8),
        if (knownPeople.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Text('Aucune personne enregistree. Placez-vous devant la camera du PC et cliquez ci-dessus.'),
            ),
          )
        else
          ...knownPeople.map((name) => Card(
                child: ListTile(
                  leading: const CircleAvatar(
                    backgroundColor: Color(0xFF18181C),
                    child: Icon(Icons.person_outline, color: Color(0xFF10B981)),
                  ),
                  title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: const Text('Ouverture automatique SFace Local'),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                    onPressed: () => _deletePerson(name),
                  ),
                ),
              )),
      ],
    );
  }

  void _showSettingsDialog() {
    final ctrl = TextEditingController(text: backendUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Connexion Serveur PC / VPS'),
        content: TextField(
          controller: ctrl,
          decoration: const InputDecoration(
            labelText: 'Adresse URL (PC Wi-Fi ou VPS)',
            hintText: 'http://172.16.19.206:8085',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          ElevatedButton(
            onPressed: () async {
              final url = ctrl.text.trim().replaceAll(RegExp(r'/$'), '');
              final prefs = await SharedPreferences.getInstance();
              await prefs.setString('backend_url', url);
              if (mounted) setState(() => backendUrl = url);
              if (ctx.mounted) Navigator.pop(ctx);
              _refreshAll();
            },
            child: const Text('Connecter'),
          ),
        ],
      ),
    );
  }
}

class EventDetailScreen extends StatelessWidget {
  final DoorEvent event;
  const EventDetailScreen({super.key, required this.event});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(event.personLabel)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (event.imageUrl != null)
            ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: Image.network(
                event.imageUrl!,
                height: 290,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),
          const SizedBox(height: 16),
          Text(event.caption, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Text('Identite locale : ${event.personLabel}', style: const TextStyle(color: Color(0xFF10B981))),
          Text('Horodatage : ${event.timestamp}', style: const TextStyle(color: Colors.white60)),
        ],
      ),
    );
  }
}
