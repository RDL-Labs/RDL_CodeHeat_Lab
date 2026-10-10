# RDL CodeHeat Lab

コードの処理負荷を有限に観測する、独立した開発用プロトコルと実験系。
GameAI個体の判断・記憶・行動権限には接続しません。

## 初版でできること

- 明示した処理区間を `perf_counter_ns` で測り、JSON互換イベントへ変換。
- 固定した局所モデルと実測の差を比較。
- 差の蓄積が閾値を越えると、有限回数の `detail_requested` を返す。
- 再送の二重計上、同IDの内容変更、別run、時間逆転、容量超過を検査。
- 想定どおりでも高コストな処理を見失わないよう、絶対消費量も保持。

```text
明示した処理境界・入力規模・環境
  → spanイベント
  → 固定モデルによる期待時間
  → 実測との差 E
  → 局所残存 H / θ
  → 詳細計測の要求 → 有限回数で粗い計測へ戻る
```

これは **RDLを参考にした局所的な性能観測実験**です。記号名が同じでも
canonical M_B / E / H や T1 の実装互換性を主張しません。
モデルは手動で固定し、学習・採用・自動再構成は未実装です。

## 実行

Python 3.11以上、実行時の外部依存なし。リポジトリ直下で:

```sh
python -m unittest discover -s tests -v
python -m codeheat
```

デモは合成イベントによる状態遷移であり、性能改善の証拠ではありません。

```python
from codeheat.collector import span

events = []
with span(events.append, run="trial-1", scope="observation",
          environment="linux-python312-build1", workload="ray-cast-v1",
          work_units=100):
    # ここで測定対象の処理を実行する
    pass
```

同一scopeは順次実行に限定します。並行workerには別scopeを割り当てます。
計測はwall timeなので、CPU時間・待機・他プロセスの影響を分離しません。
入れ子区間は包含時間です。親子の時間を単純合算してはいけません。

## 現在の停止境界

`detail_requested` は要求の出力です。実関数の自動追跡・計測解像度変更は
接続先adapterの責務で、初版はまだ自動接続していません。
メモリ計測、フレームグラフ、GameAI接続、プロファイラ自動起動、コードの
自動修正は未実装です。まず再現可能なプロトコルを検証します。

詳細: [プロトコル](docs/PROTOCOL.md)、[工程表](docs/PLAN.md)。
