# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"D:\重构python\kwzy-python\docs\04-api\openapi-v1-core.yaml")
c = p.read_text(encoding="utf-8")

new = """  /collection/cases:
    get:
      tags: [Collection]
      summary: 催缴案件列表
      operationId: listCollectionCases
      security: [{ bearerAuth: [] }]
      parameters:
        - $ref: '#/components/parameters/Page'
        - $ref: '#/components/parameters/PageSize'
        - name: park_id
          in: query
          schema: { type: integer, format: int64 }
        - name: status
          in: query
          schema: { type: string }
        - name: bill_id
          in: query
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CollectionCasePage'
    post:
      tags: [Collection]
      summary: 创建催缴案件
      operationId: createCollectionCase
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CollectionCaseCreate'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CollectionCaseEnvelope'

  /collection/cases/{case_id}:
    get:
      tags: [Collection]
      summary: 催缴案件详情（含 records）
      operationId: getCollectionCase
      security: [{ bearerAuth: [] }]
      parameters:
        - name: case_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CollectionCaseDetailEnvelope'
    patch:
      tags: [Collection]
      summary: 更新案件状态/级别/跟进人
      operationId: updateCollectionCase
      security: [{ bearerAuth: [] }]
      parameters:
        - name: case_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CollectionCaseUpdate'
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CollectionCaseEnvelope'

  /collection/cases/{case_id}/records:
    get:
      tags: [Collection]
      summary: 催缴记录列表
      operationId: listCollectionRecords
      security: [{ bearerAuth: [] }]
      parameters:
        - name: case_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CollectionRecordListEnvelope'
    post:
      tags: [Collection]
      summary: 追加催缴记录
      operationId: createCollectionRecord
      security: [{ bearerAuth: [] }]
      parameters:
        - name: case_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CollectionRecordCreate'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CollectionRecordEnvelope'

"""

if "/collection/cases/{case_id}/records" not in c:
    if "  /collection/cases:" in c and "  /collection/sms/preview:" in c:
        start = c.index("  /collection/cases:")
        end = c.index("  /collection/sms/preview:")
        c = c[:start] + new + "\n" + c[end:]
    elif "  /collection/sms/preview:" in c:
        c = c.replace("  /collection/sms/preview:", new + "  /collection/sms/preview:", 1)
    else:
        raise SystemExit("insert point missing")

schemas_add = """
    CollectionCaseCreate:
      type: object
      required: [park_id, party_id, bill_id]
      properties:
        park_id: { type: integer, format: int64 }
        party_id: { type: integer, format: int64 }
        bill_id: { type: integer, format: int64 }
        level: { type: string, default: L1 }
        assignee_id: { type: integer, format: int64, nullable: true }
        remark: { type: string }
    CollectionCaseUpdate:
      type: object
      properties:
        status: { type: string }
        level: { type: string }
        assignee_id: { type: integer, format: int64, nullable: true }
        next_action_at: { type: string, format: date-time, nullable: true }
    CollectionCase:
      type: object
      properties:
        id: { type: integer, format: int64 }
        park_id: { type: integer, format: int64 }
        party_id: { type: integer, format: int64 }
        bill_id: { type: integer, format: int64 }
        status: { type: string }
        level: { type: string }
        assignee_id: { type: integer, format: int64, nullable: true }
        open_amount_snapshot: { type: number, nullable: true }
        next_action_at: { type: string, format: date-time, nullable: true }
    CollectionRecord:
      type: object
      properties:
        id: { type: integer, format: int64 }
        case_id: { type: integer, format: int64 }
        record_type: { type: string, description: 'SMS|CALL|VISIT|NOTE|SYSTEM' }
        content: { type: string, nullable: true }
        result: { type: string, nullable: true }
        channel_ref: { type: string, nullable: true }
        created_by: { type: integer, format: int64, nullable: true }
        created_at: { type: string, format: date-time }
    CollectionRecordCreate:
      type: object
      required: [record_type]
      properties:
        record_type: { type: string }
        content: { type: string }
        result: { type: string }
    CollectionCaseEnvelope:
      type: object
      properties:
        code: { type: string }
        message: { type: string }
        data: { $ref: '#/components/schemas/CollectionCase' }
    CollectionCaseDetailEnvelope:
      type: object
      properties:
        code: { type: string }
        message: { type: string }
        data:
          type: object
          properties:
            case: { $ref: '#/components/schemas/CollectionCase' }
            records:
              type: array
              items: { $ref: '#/components/schemas/CollectionRecord' }
    CollectionRecordEnvelope:
      type: object
      properties:
        code: { type: string }
        message: { type: string }
        data: { $ref: '#/components/schemas/CollectionRecord' }
    CollectionRecordListEnvelope:
      type: object
      properties:
        code: { type: string }
        message: { type: string }
        data:
          type: object
          properties:
            items:
              type: array
              items: { $ref: '#/components/schemas/CollectionRecord' }
"""

if "CollectionRecordCreate:" not in c:
    if "    CollectionCasePage:" in c:
        # Expand CollectionCasePage area - insert before Payment if exists after
        if "    AiJob:" in c:
            c = c.replace("    AiJob:", schemas_add + "\n    AiJob:", 1)
        elif "    CollectionCasePage:" in c:
            # after CollectionCase definition block - append near PaymentAllocation
            marker = "    PaymentAllocationInput:"
            if marker in c:
                c = c.replace(marker, schemas_add + "\n" + marker, 1)
            else:
                c = c.rstrip() + "\n" + schemas_add + "\n"
    else:
        c = c.rstrip() + "\n" + schemas_add + "\n"

c = c.replace(
    "summary: 收款登记并核销账单（非在线支付下单）",
    "summary: 收款登记并核销账单（非在线支付；allocations 分摊核销，支持部分收款）",
)

# PaymentCreate description
if "PaymentCreate:" in c and "分摊核销" not in c[c.find("PaymentCreate:") : c.find("PaymentCreate:") + 400]:
    c = c.replace(
        """    PaymentCreate:
      type: object
      required: [park_id, party_id, amount, paid_at, allocations]
      properties:""",
        """    PaymentCreate:
      type: object
      description: 收款登记；allocations 将金额分摊到一张或多张账单（部分/全额核销）
      required: [park_id, party_id, amount, paid_at, allocations]
      properties:""",
        1,
    )

p.write_text(c, encoding="utf-8")
print("records path", "/collection/cases/{case_id}/records" in c)
print("CollectionRecordCreate", "CollectionRecordCreate:" in c)
