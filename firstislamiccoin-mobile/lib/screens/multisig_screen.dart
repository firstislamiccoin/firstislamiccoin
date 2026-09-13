/// UI on top of crypto/transaction.dart's already-complete multisig
/// primitives (see that file's comment block for the full design
/// reasoning). Proposals are signed sequentially -- cosigner A signs the
/// JSON, sends it to B, B signs the same object, and so on -- which
/// reaches any m-of-n threshold without needing an explicit
/// "combine independently-signed copies" step (mergeMultisigProposals
/// exists for that parallel case but isn't wired into this screen, a
/// deliberate scope cut). This wallet's own multisig identity is always
/// index 0's key (WalletService.multisigKey), independent of whichever
/// address is "active" for receiving.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../crypto/address.dart';
import '../crypto/transaction.dart' as tx;
import '../services/wallet_service.dart';
import 'qr_scan_screen.dart';

// ~1500 chars is a conservative cutoff for reliable scanning at a
// reasonable QR size/zoom, well under the encoder's own hard limit -- a
// multisig proposal with several inputs can exceed it, so this fails
// closed with a clear message rather than silently producing an
// unscannable QR. Matches web-wallet's identical cutoff.
const _msQrMaxChars = 1500;

String _bytesToHex(Uint8List b) => b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
Uint8List _hexToBytes(String hex) {
  final out = Uint8List(hex.length ~/ 2);
  for (var i = 0; i < out.length; i++) {
    out[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return out;
}

class MultisigScreen extends StatefulWidget {
  const MultisigScreen({super.key});

  @override
  State<MultisigScreen> createState() => _MultisigScreenState();
}

class _MultisigScreenState extends State<MultisigScreen> {
  String? _myPubkeyHex;

  final _pubkeysController = TextEditingController();
  final _mController = TextEditingController(text: '2');
  String? _createError;
  String? _redeemScriptHex;
  String? _msAddress;

  final _proposeAddressController = TextEditingController();
  final _proposeRedeemController = TextEditingController();
  final _proposeToController = TextEditingController();
  final _proposeAmountController = TextEditingController();
  String? _proposeError;

  final _proposalJsonController = TextEditingController();
  String? _signError;
  String? _signSuccess;

  @override
  void initState() {
    super.initState();
    _loadMyPubkey();
  }

  Future<void> _loadMyPubkey() async {
    final key = await context.read<WalletService>().multisigKey();
    if (mounted) setState(() => _myPubkeyHex = _bytesToHex(key.publicKey));
  }

  Future<void> _createAddress() async {
    setState(() => _createError = null);
    try {
      final wallet = context.read<WalletService>();
      final key = await wallet.multisigKey();
      final lines = _pubkeysController.text
          .trim()
          .split('\n')
          .map((l) => l.trim())
          .where((l) => l.isNotEmpty)
          .toList();
      final cosignerPubkeys = lines.map(_hexToBytes).toList();
      final allPubkeys = [key.publicKey, ...cosignerPubkeys];
      final m = int.parse(_mController.text.trim());
      final redeemScript = tx.createMultisigRedeemScript(m, allPubkeys);
      final address = tx.multisigAddress(redeemScript, wallet.network);
      setState(() {
        _redeemScriptHex = _bytesToHex(redeemScript);
        _msAddress = address;
        _proposeAddressController.text = address;
        _proposeRedeemController.text = _bytesToHex(redeemScript);
      });
    } catch (e) {
      setState(() => _createError = e.toString());
    }
  }

  Future<void> _createProposal() async {
    setState(() => _proposeError = null);
    try {
      final wallet = context.read<WalletService>();
      final address = _proposeAddressController.text.trim();
      final redeemScriptHex = _proposeRedeemController.text.trim();
      final toAddress = _proposeToController.text.trim();
      final amountFic = double.tryParse(_proposeAmountController.text.trim());
      if (address.isEmpty || redeemScriptHex.isEmpty || toAddress.isEmpty || amountFic == null || amountFic <= 0) {
        setState(() => _proposeError = 'Fill in every field.');
        return;
      }
      final redeemScript = _hexToBytes(redeemScriptHex);
      final decoded = decodeAddress(toAddress, wallet.network);
      final Uint8List outScript;
      switch (decoded.type) {
        case AddressType.p2pkh:
          outScript = tx.p2pkhScriptPubKey(decoded.hash);
        case AddressType.p2sh:
          outScript = tx.p2shScriptPubKey(decoded.hash);
        case AddressType.p2wpkh:
          outScript = tx.p2wpkhScriptPubKey(decoded.hash);
      }
      final amountSatoshis = (amountFic * 100000000).round();

      final utxoResp = await wallet.gateway.utxos(address);
      final utxoList = utxoResp['utxos'] as List<dynamic>? ?? const [];
      final feeResp = await wallet.gateway.feeEstimate();
      final feeRate = int.tryParse(feeResp['fee_rate_sat_per_vbyte']?.toString() ?? '') ?? 1;

      var totalIn = 0;
      final chosen = <Map<String, dynamic>>[];
      for (final u in utxoList) {
        final m = u as Map<String, dynamic>;
        chosen.add(m);
        totalIn += int.parse(m['value'].toString());
        // Multisig scriptSigs run much larger than a plain P2PKH spend
        // (one DER signature per required cosigner, plus the redeem
        // script itself) -- deliberately generous, not precise, same
        // "no real dynamic fee estimation" limitation as the ordinary
        // send flow.
        final estimatedVsize = 10 + chosen.length * (redeemScript.length + 150) + 2 * 34;
        final feeSatoshis = (feeRate * estimatedVsize + 999) ~/ 1000;
        if (totalIn >= amountSatoshis + feeSatoshis) break;
      }
      final finalVsize = 10 + chosen.length * (redeemScript.length + 150) + 2 * 34;
      final feeSatoshis = (feeRate * finalVsize + 999) ~/ 1000;
      if (totalIn < amountSatoshis + feeSatoshis) {
        setState(() => _proposeError =
            'Insufficient funds at this address: have $totalIn, need ${amountSatoshis + feeSatoshis}');
        return;
      }
      final change = totalIn - amountSatoshis - feeSatoshis;

      final inputs = chosen
          .map((m) => tx.Utxo(
                txid: _reverseHexBytes(m['txid'] as String),
                vout: m['vout'] as int,
                valueSatoshis: int.parse(m['value'].toString()),
                pubkeyHash: Uint8List(20), // unused for multisig proposals (redeemScript is the subscript)
              ))
          .toList();
      final outputs = <tx.TxOutputSpec>[
        tx.TxOutputSpec(outScript, amountSatoshis),
        if (change > 0) tx.TxOutputSpec(tx.p2shScriptPubKey(hash160(redeemScript)), change),
      ];
      final proposal = tx.createMultisigProposal(
        inputs: inputs,
        redeemScripts: [for (var _ in inputs) redeemScript],
        outputs: outputs,
      );
      setState(() => _proposalJsonController.text = const JsonEncoder.withIndent('  ').convert(proposal.toJson()));
    } catch (e) {
      setState(() => _proposeError = e.toString());
    }
  }

  Uint8List _reverseHexBytes(String hex) {
    final bytes = _hexToBytes(hex);
    return Uint8List.fromList(bytes.reversed.toList());
  }

  Future<void> _signProposal() async {
    setState(() {
      _signError = null;
      _signSuccess = null;
    });
    try {
      final wallet = context.read<WalletService>();
      final key = await wallet.multisigKey();
      final proposal = tx.MultisigProposal.fromJson(jsonDecode(_proposalJsonController.text) as Map<String, dynamic>);
      tx.signMultisigProposal(proposal, key.privateKey, key.publicKey);
      setState(() {
        _proposalJsonController.text = const JsonEncoder.withIndent('  ').convert(proposal.toJson());
        _signSuccess = 'Signed with your key. Send this JSON to the next cosigner, or finalize if enough signatures are collected.';
      });
    } catch (e) {
      setState(() => _signError = e.toString());
    }
  }

  Future<void> _showProposalQr() async {
    final json = _proposalJsonController.text.trim();
    if (json.isEmpty) return;
    if (json.length > _msQrMaxChars) {
      setState(() => _signError =
          'This proposal is too large for a reliable QR code (${json.length} characters). Share the JSON text directly instead.');
      return;
    }
    setState(() => _signError = null);
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Scan this on another device'),
        content: SizedBox(
          width: 260,
          height: 260,
          child: Container(
            color: Colors.white,
            padding: const EdgeInsets.all(12),
            child: QrImageView(data: json, version: QrVersions.auto),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Close'))],
      ),
    );
  }

  Future<void> _scanProposalQr() async {
    final result = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScanScreen(title: 'Scan proposal')),
    );
    if (result != null) {
      setState(() => _proposalJsonController.text = result);
    }
  }

  Future<void> _finalizeAndBroadcast() async {
    setState(() {
      _signError = null;
      _signSuccess = null;
    });
    try {
      final wallet = context.read<WalletService>();
      final proposal = tx.MultisigProposal.fromJson(jsonDecode(_proposalJsonController.text) as Map<String, dynamic>);
      final rawTx = tx.finalizeMultisigTransaction(proposal);
      final hex = rawTx.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      final txid = await wallet.gateway.broadcast(hex);
      setState(() => _signSuccess = 'Broadcast: $txid');
    } catch (e) {
      setState(() => _signError = e.toString());
    }
  }

  @override
  void dispose() {
    _pubkeysController.dispose();
    _mController.dispose();
    _proposeAddressController.dispose();
    _proposeRedeemController.dispose();
    _proposeToController.dispose();
    _proposeAmountController.dispose();
    _proposalJsonController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Multisig')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Text(
            'Create a shared N-of-M address, propose a spend, collect '
            'signatures from cosigners, and broadcast once enough have '
            'signed. Proposals are plain JSON -- send them to cosigners '
            'however you like (email, a shared file); nothing here '
            'transmits them for you.',
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 24),
          Text('1. Create a multisig address', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          Text(
            'Your own compressed public key (included automatically): ${_myPubkeyHex ?? '...'}',
            style: const TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _pubkeysController,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: "Cosigners' public keys (one per line, 33-byte compressed hex)",
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _mController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Signatures required (M)', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          FilledButton(onPressed: _createAddress, child: const Text('Generate address')),
          if (_createError != null) Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(_createError!, style: const TextStyle(color: Colors.red)),
          ),
          if (_msAddress != null) Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Redeem script (share with cosigners -- required to spend)', style: TextStyle(fontSize: 12, color: Colors.grey)),
                SelectableText(_redeemScriptHex!, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                const SizedBox(height: 8),
                const Text('Multisig address', style: TextStyle(fontSize: 12, color: Colors.grey)),
                SelectableText(_msAddress!, style: const TextStyle(fontFamily: 'monospace', fontSize: 13)),
              ],
            ),
          ),
          const Divider(height: 40),
          Text('2. Propose a spend', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          TextField(controller: _proposeAddressController, decoration: const InputDecoration(labelText: 'Multisig address (must have funds)', border: OutlineInputBorder())),
          const SizedBox(height: 8),
          TextField(controller: _proposeRedeemController, maxLines: 2, decoration: const InputDecoration(labelText: 'Redeem script (hex)', border: OutlineInputBorder())),
          const SizedBox(height: 8),
          TextField(controller: _proposeToController, decoration: const InputDecoration(labelText: 'Destination address', border: OutlineInputBorder())),
          const SizedBox(height: 8),
          TextField(controller: _proposeAmountController, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'Amount (FIC)', border: OutlineInputBorder())),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _createProposal, child: const Text('Create proposal')),
          if (_proposeError != null) Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(_proposeError!, style: const TextStyle(color: Colors.red)),
          ),
          const Divider(height: 40),
          Text('3. Sign / finalize / broadcast a proposal', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          TextField(
            controller: _proposalJsonController,
            maxLines: 8,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
            decoration: const InputDecoration(labelText: 'Proposal JSON (paste one)', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: OutlinedButton(onPressed: _showProposalQr, child: const Text('Show as QR'))),
              const SizedBox(width: 8),
              Expanded(child: OutlinedButton(onPressed: _scanProposalQr, child: const Text('Scan QR'))),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: OutlinedButton(onPressed: _signProposal, child: const Text('Sign with my key'))),
              const SizedBox(width: 8),
              Expanded(child: OutlinedButton(onPressed: _finalizeAndBroadcast, child: const Text('Finalize & broadcast'))),
            ],
          ),
          if (_signError != null) Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(_signError!, style: const TextStyle(color: Colors.red)),
          ),
          if (_signSuccess != null) Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(_signSuccess!, style: const TextStyle(color: Colors.green)),
          ),
        ],
      ),
    );
  }
}
