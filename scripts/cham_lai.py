#!/usr/bin/env python
"""Dựng phiếu chấm mù lại cho một bộ đã có nhãn tay.

Nhãn tay là ĐÁP ÁN của mọi bảng số judge, nên nó cũng có lỗi như mọi thứ khác — và sửa lẻ một câu
sau khi đã xem judge chấm là cách tự lừa mình: lần sau không biết đáp án phản ánh tài liệu hay
phản ánh judge. Cách sạch là chấm mù lại cả bộ.

Phiếu ra: thứ tự xáo, id đổi thành c01..cNN, KHÔNG có nhãn tay cũ và KHÔNG có nhãn judge. Chunk in
kèm ngay dưới từng câu để khỏi phải mở data/kb/ tra tay — bớt một nguồn lỗi.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.corpus import ROOT, load_kb  # noqa: E402

BO = {
    "dev": ROOT / "data" / "faithfulness.yml",
    "xacnhan": ROOT / "data" / "faithfulness_xacnhan.yml",
}

HUONG_DAN = """# CHẤM MÙ LẠI — bộ {bo}, {n} câu, seed {seed}
# Giải thích đầy đủ: data/HUONG_DAN_CHAM.md
#
# Mỗi câu đi từ trên xuống, khớp ở đâu dừng ở đó:
#
#   1. Bot nói điều gì mà chunks KHÔNG đỡ được?      -> bia
#   2. Bot nói được thứ ĐÚNG Ý khách hỏi?            -> co_can_cu
#   3. Bot không trả lời. Chunks có sẵn câu trả lời?
#        có     -> tu_choi_thua
#        không  -> tu_choi_dung
#
# KHÔNG tính là "bot nói": chào hỏi, xin lỗi, hỏi lại khách, "mình chưa có thông tin",
# "liên hệ tổng đài" chung chung, nhắc lại lời khách vừa nói.
#
# chac_chan: cao / thap. Phân vân cứ ghi thap và nói vì sao ở ghi_chu — câu thap được tính
# riêng chứ không bị vứt. Phân vân nhiều là KẾT QUẢ, không phải bạn chấm kém.
#
# Chấm xong hết mới mở: {stem}.yml, judge_compare/, {stem}_dapan.yml, {stem}_chamlai_map.yml
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bo", choices=tuple(BO), default="xacnhan")
    parser.add_argument("--seed", type=int, default=16, help="seed xáo thứ tự, ghi vào phiếu")
    args = parser.parse_args(argv)

    goc = yaml.safe_load(BO[args.bo].read_text(encoding="utf-8"))
    by_id = {chunk.doc_id: chunk for chunk in load_kb()}

    thu_tu = list(goc)
    random.Random(args.seed).shuffle(thu_tu)

    phieu, anh_xa = [], {}
    for i, item in enumerate(thu_tu, start=1):
        moi = f"c{i:02d}"
        anh_xa[moi] = item["id"]
        phieu.append(
            {
                "id": moi,
                "query": item["query"],
                "tra_loi": item["tra_loi"],
                # In nguyên văn chunk: chấm mà phải mở file khác tra tay là thêm một nguồn lỗi.
                "chunks_day_du": [
                    {"docId": d, "title": by_id[d].title, "content": by_id[d].content}
                    for d in item["chunks"]
                ],
                "nhan_tay": None,
                "chac_chan": None,
                "ghi_chu": None,
            }
        )

    ra = BO[args.bo].with_name(f"{BO[args.bo].stem}_chamlai.yml")
    # Giữ nhãn đã chấm: sinh lại phiếu không được xoá công của người chấm.
    cu = {}
    if ra.exists():
        for item in yaml.safe_load(ra.read_text(encoding="utf-8")) or []:
            if any(item.get(k) for k in ("nhan_tay", "chac_chan", "ghi_chu")):
                cu[item["id"]] = item
    giu = 0
    for item in phieu:
        if (truoc := cu.get(item["id"])) is not None:
            for k in ("nhan_tay", "chac_chan", "ghi_chu"):
                item[k] = truoc.get(k)
            giu += 1

    # Nhắc cây quyết định NGAY TRÊN ô điền: chunk dài, cuộn ngược lên đầu file là việc thừa.
    nhac = """  # bia = có ý chunks không đỡ | co_can_cu = đúng ý khách hỏi
  # tu_choi_thua = chunks có sẵn mà bot không dùng | tu_choi_dung = chunks không có
  nhan_tay:"""
    than = [
        yaml.safe_dump([item], allow_unicode=True, sort_keys=False, width=100).replace(
            "  nhan_tay:", nhac
        )
        for item in phieu
    ]
    ra.write_text(
        HUONG_DAN.format(bo=args.bo, n=len(phieu), seed=args.seed, stem=BO[args.bo].stem)
        + "".join(than),
        encoding="utf-8",
    )
    if giu:
        print(f"Giữ lại {giu} câu đã chấm.")
    ra_map = BO[args.bo].with_name(f"{BO[args.bo].stem}_chamlai_map.yml")
    ra_map.write_text(
        "# Ánh xạ id phiếu -> id gốc. KHÔNG mở trước khi chấm xong.\n"
        + yaml.safe_dump(anh_xa, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Phiếu chấm : {ra.relative_to(ROOT)}  ({len(phieu)} câu, seed {args.seed})")
    print(f"Ánh xạ id  : {ra_map.relative_to(ROOT)}  — đừng mở trước khi chấm xong")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
