<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Intelligence Room</title>

    <style>
        body{
            margin:0;
            background:#0f172a;
            color:white;
            font-family:Arial,sans-serif;
            padding:40px;
        }

        .container{
            max-width:1100px;
            margin:auto;
        }

        h1{
            margin-bottom:10px;
        }

        .card{
            background:#1e293b;
            border-radius:20px;
            padding:20px;
            margin-bottom:20px;
        }

        .number{
            font-size:34px;
            font-weight:bold;
        }

        .grid{
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
            gap:20px;
        }

        table{
            width:100%;
            border-collapse:collapse;
        }

        td,th{
            padding:14px;
            border-bottom:1px solid rgba(255,255,255,.1);
            text-align:right;
        }

        .green{
            color:#22c55e;
        }

        .red{
            color:#ef4444;
        }

        .yellow{
            color:#facc15;
        }
    </style>
</head>
<body>

<div class="container">

    <h1>⬡ Intelligence Room Dashboard</h1>
    <p>מערכת ניהול בוט</p>

    <div class="grid">

        <div class="card">
            <h3>👥 משתמשים</h3>
            <div class="number">
                {{ total_users }}
            </div>
        </div>

        <div class="card">
            <h3>✅ מנויים פעילים</h3>
            <div class="number green">
                {{ active_users }}
            </div>
        </div>

        <div class="card">
            <h3>⏳ ממתינים לאישור</h3>
            <div class="number yellow">
                {{ pending_users }}
            </div>
        </div>

        <div class="card">
            <h3>🚫 חסומים</h3>
            <div class="number red">
                {{ blocked_users }}
            </div>
        </div>

    </div>

    <div class="card">
        <h2>📋 משתמשים אחרונים</h2>

        <table>
            <thead>
                <tr>
                    <th>שם משתמש</th>
                    <th>ID</th>
                    <th>מנוי</th>
                    <th>תוקף</th>
                </tr>
            </thead>

            <tbody>

            {% for user in users %}
            <tr>
                <td>{{ user.username }}</td>
                <td>{{ user.user_id }}</td>
                <td>{{ user.plan }}</td>
                <td>{{ user.expiry }}</td>
            </tr>
            {% endfor %}

            </tbody>
        </table>

    </div>

</div>

</body>
</html>
