# Showcase — Pallet ID = warehouse placement validated

## The idea (simple)

```text
  Pallet arrives / is placed at the warehouse location
              │
              ▼
  Operator types pallet number on 4×4 keypad
              │
              ▼
  Presses A  ──►  Cloud stores: “this pallet ID is registered as PLACED”
              │
              ▼
  Mentor downloads Excel → proof / audit list
              │
              ▼
  Wrong entry? Only administrator can VOID it
```

| In plain words | In the system |
|----------------|---------------|
| “We logged that pallet **1042** is in the warehouse” | MQTT → cloud row with `status: placed` |
| “Show me everything that was logged today” | **Download Excel** (`.xls` / `.csv` opens in Excel) |
| “That ID was a mistake” | Admin login → **Void** (operators cannot delete) |

## Why this is useful for validation

1. **Traceability** — every placed pallet has a digital ID + timestamp + station.  
2. **No paper pad** — keypad + cloud instead of handwritten lists.  
3. **Controlled correction** — operators add; admins only remove/void.  
4. **Demo-friendly** — type ID → A → refresh browser → see row → download Excel.

## Operator story (30 seconds)

1. LCD: `Enter pallet`  
2. Type `1042` → LCD: `ID: 1042`  
3. Press **A** → LCD: `Placed OK`  
4. Browser `http://LAPTOP:3081` shows pallet **1042**, status **placed**, purpose **Warehouse placement validated**  
5. Click **Download Excel** → open in Microsoft Excel  

## Status meanings

| Status | Meaning |
|--------|---------|
| **placed** | Operator pressed A — pallet ID accepted as **successfully placed / validated** in the warehouse log |
| **void** | Admin cancelled a wrong ID (soft delete; history kept) |

## What “stored in cloud” means technically

- Laptop runs Project 2 cloud (port **3081**).  
- ESP publishes JSON to MQTT topic `callstation/pallet/record`.  
- Cloud saves to `cloud/data/pallets.json` and shows it on the web page.  
- Download = export of that list for Excel (local laptop server unless you host it elsewhere later).
