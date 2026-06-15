"""
MOV → MP4 変換ツール（Windows用）
H.265/HEVCのMOVファイルをH.264のMP4に変換します
ffmpegが必要です（同じフォルダに置くか、PATHに通す）

使い方:
  1. ffmpeg.exe をこのスクリプトと同じフォルダに置く
  2. python mov_converter.py で起動
  3. ファイルを追加 or ドラッグ＆ドロップ → 変換開始
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import os
import sys
import shutil
import re
from pathlib import Path


def find_ffmpeg():
    """ffmpeg.exe を探す: スクリプトと同フォルダ → PATH の順"""
    script_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    local = script_dir / 'ffmpeg.exe'
    if local.exists():
        return str(local)
    found = shutil.which('ffmpeg')
    return found  # None の場合もある


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('MOV → MP4 変換ツール')
        self.geometry('640x540')
        self.resizable(True, True)
        self.configure(bg='#f5f5f5')

        self.files = []
        self.converting = False
        self._outdir = None
        self._ffmpeg = find_ffmpeg()

        self._build_ui()
        self._setup_dnd()

    # ── UI ────────────────────────────────────────────
    def _build_ui(self):
        # タイトル
        tk.Label(self, text='MOV → MP4 変換ツール',
                 font=('Yu Gothic UI', 14, 'bold'),
                 bg='#f5f5f5', fg='#222').pack(pady=(16, 2))
        tk.Label(self,
                 text='iPhoneで撮影したH.265/HEVC動画をブラウザで再生できるMP4に変換します',
                 font=('Yu Gothic UI', 9), bg='#f5f5f5', fg='#666').pack(pady=(0, 10))

        # ファイルエリア
        frame_files = tk.LabelFrame(self, text='変換するファイル',
                                    font=('Yu Gothic UI', 9), padx=8, pady=8,
                                    bg='#f5f5f5', fg='#444')
        frame_files.pack(fill='both', expand=True, padx=14, pady=(0, 6))

        list_frame = tk.Frame(frame_files, bg='#f5f5f5')
        list_frame.pack(fill='both', expand=True)
        sb = ttk.Scrollbar(list_frame, orient='vertical')
        self.listbox = tk.Listbox(list_frame, selectmode='extended',
                                  font=('Yu Gothic UI', 9), bg='white',
                                  relief='flat', highlightthickness=1,
                                  highlightbackground='#ddd', activestyle='none',
                                  yscrollcommand=sb.set)
        sb.configure(command=self.listbox.yview)
        sb.pack(side='right', fill='y')
        self.listbox.pack(side='left', fill='both', expand=True)

        self.drop_hint = tk.Label(frame_files,
                                  text='ここにMOVファイルをドラッグ＆ドロップ（またはボタンで追加）',
                                  font=('Yu Gothic UI', 9), bg='#f5f5f5', fg='#aaa')
        self.drop_hint.pack(pady=(5, 0))

        btn_row = tk.Frame(frame_files, bg='#f5f5f5')
        btn_row.pack(fill='x', pady=(6, 0))
        for text, cmd, bg in [
            ('＋ ファイルを追加', self._add_files, '#388ADD'),
            ('選択を削除',        self._remove_selected, '#e0e0e0'),
            ('全てクリア',        self._clear_all, '#e0e0e0'),
        ]:
            fg = 'white' if bg == '#388ADD' else '#333'
            tk.Button(btn_row, text=text, command=cmd,
                      font=('Yu Gothic UI', 9), bg=bg, fg=fg,
                      relief='flat', padx=10, pady=4,
                      cursor='hand2').pack(side='left', padx=(0, 6))

        # 出力設定
        frame_opt = tk.LabelFrame(self, text='出力設定',
                                  font=('Yu Gothic UI', 9), padx=8, pady=8,
                                  bg='#f5f5f5', fg='#444')
        frame_opt.pack(fill='x', padx=14, pady=(0, 6))

        row1 = tk.Frame(frame_opt, bg='#f5f5f5')
        row1.pack(fill='x', pady=(0, 4))
        tk.Label(row1, text='出力先:', font=('Yu Gothic UI', 9),
                 bg='#f5f5f5', width=10, anchor='w').pack(side='left')
        self.out_var = tk.StringVar(value='元のファイルと同じフォルダ')
        tk.Entry(row1, textvariable=self.out_var, font=('Yu Gothic UI', 9),
                 state='readonly', relief='flat', bg='#eee',
                 readonlybackground='#eee').pack(side='left', fill='x', expand=True, padx=(0, 6))
        tk.Button(row1, text='変更', command=self._choose_outdir,
                  font=('Yu Gothic UI', 9), bg='#e0e0e0', fg='#333',
                  relief='flat', padx=8, pady=2, cursor='hand2').pack(side='left')

        row2 = tk.Frame(frame_opt, bg='#f5f5f5')
        row2.pack(fill='x')
        tk.Label(row2, text='品質 (CRF):', font=('Yu Gothic UI', 9),
                 bg='#f5f5f5', width=10, anchor='w').pack(side='left')
        self.crf_var = tk.IntVar(value=23)
        tk.Scale(row2, from_=18, to=28, orient='horizontal',
                 variable=self.crf_var, length=160,
                 bg='#f5f5f5', troughcolor='#ddd',
                 font=('Yu Gothic UI', 8)).pack(side='left')
        tk.Label(row2, text='← 高品質（ファイル大）　低品質（ファイル小）→',
                 font=('Yu Gothic UI', 8), bg='#f5f5f5', fg='#888').pack(side='left', padx=8)

        # 進捗
        frame_prog = tk.Frame(self, bg='#f5f5f5')
        frame_prog.pack(fill='x', padx=14, pady=(0, 4))
        self.status_var = tk.StringVar(value='待機中')
        tk.Label(frame_prog, textvariable=self.status_var,
                 font=('Yu Gothic UI', 9), bg='#f5f5f5', fg='#555',
                 anchor='w').pack(fill='x')
        self.progress = ttk.Progressbar(frame_prog, mode='determinate')
        self.progress.pack(fill='x', pady=(3, 0))

        # 変換ボタン
        self.conv_btn = tk.Button(self, text='▶ 変換開始',
                                  command=self._start_convert,
                                  font=('Yu Gothic UI', 11, 'bold'),
                                  bg='#388ADD', fg='white', relief='flat',
                                  padx=24, pady=8, cursor='hand2')
        self.conv_btn.pack(pady=(6, 4))

        # ffmpeg 状態
        if self._ffmpeg:
            msg = f'ffmpeg: {self._ffmpeg}'
            fg = '#4caf50'
        else:
            msg = '⚠ ffmpeg が見つかりません — ffmpeg.exe をこのスクリプトと同じフォルダに置いてください'
            fg = '#e53935'
        tk.Label(self, text=msg, font=('Yu Gothic UI', 8),
                 bg='#f5f5f5', fg=fg, wraplength=600).pack(pady=(0, 10))

    # ── ドラッグ＆ドロップ ────────────────────────────
    def _setup_dnd(self):
        try:
            self.listbox.drop_target_register('DND_Files')
            self.listbox.dnd_bind('<<Drop>>', self._on_drop)
            self.drop_hint.configure(fg='#388ADD')
        except Exception:
            pass  # tkinterdnd2 未導入でも動く

    def _on_drop(self, event):
        paths = re.findall(r'\{[^}]+\}|\S+', event.data)
        self._add_paths([p.strip('{}') for p in paths])

    # ── ファイル操作 ──────────────────────────────────
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title='動画ファイルを選択',
            filetypes=[('動画ファイル', '*.mov *.MOV *.mp4 *.MP4 *.avi *.AVI *.mkv *.MKV *.m4v'),
                       ('全てのファイル', '*.*')])
        self._add_paths(paths)

    def _add_paths(self, paths):
        for p in paths:
            p = str(p).strip()
            if p and p not in self.files:
                self.files.append(p)
                self.listbox.insert('end', Path(p).name)
        self._update_hint()

    def _remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            self.files.pop(i)
        self._update_hint()

    def _clear_all(self):
        self.listbox.delete(0, 'end')
        self.files.clear()
        self._update_hint()

    def _update_hint(self):
        if self.files:
            self.drop_hint.configure(
                text=f'{len(self.files)} 件追加済み', fg='#388ADD')
        else:
            self.drop_hint.configure(
                text='ここにMOVファイルをドラッグ＆ドロップ（またはボタンで追加）', fg='#aaa')

    def _choose_outdir(self):
        d = filedialog.askdirectory(title='出力先フォルダを選択')
        if d:
            self._outdir = d
            self.out_var.set(d)
        else:
            self._outdir = None
            self.out_var.set('元のファイルと同じフォルダ')

    # ── 変換 ─────────────────────────────────────────
    def _start_convert(self):
        if self.converting:
            return
        if not self._ffmpeg:
            messagebox.showerror('ffmpeg が見つかりません',
                'ffmpeg.exe をこのスクリプトと同じフォルダに置いてください。\n\n'
                'ダウンロード先:\nhttps://github.com/BtbN/FFmpeg-Builds/releases\n'
                '→ ffmpeg-master-latest-win64-gpl.zip をダウンロードして\n'
                '  bin/ffmpeg.exe をこのスクリプトと同じフォルダに置いてください。')
            return
        if not self.files:
            messagebox.showwarning('ファイルなし', '変換するファイルを追加してください')
            return
        self.converting = True
        self.conv_btn.configure(state='disabled', text='変換中...')
        threading.Thread(target=self._convert_all, daemon=True).start()

    def _convert_all(self):
        total = len(self.files)
        success = 0
        errors = []

        for i, src in enumerate(self.files):
            src_path = Path(src)
            out_dir = Path(self._outdir) if self._outdir else src_path.parent
            dst_path = out_dir / (src_path.stem + '_converted.mp4')

            self.after(0, self.status_var.set, f'({i+1}/{total}) 変換中: {src_path.name}')
            self.after(0, self.progress.configure, {'value': i / total * 100})

            cmd = [
                self._ffmpeg, '-y',
                '-i', str(src_path),
                '-c:v', 'libx264',
                '-crf', str(self.crf_var.get()),
                '-preset', 'fast',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                str(dst_path)
            ]
            try:
                r = subprocess.run(cmd,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                if r.returncode == 0:
                    success += 1
                else:
                    err = r.stderr.decode('utf-8', errors='ignore')[-300:]
                    errors.append(f'{src_path.name}:\n{err}')
            except Exception as e:
                errors.append(f'{src_path.name}: {e}')

        self.after(0, self.progress.configure, {'value': 100})
        self.converting = False
        self.after(0, self._on_done, success, total, errors)

    def _on_done(self, success, total, errors):
        self.conv_btn.configure(state='normal', text='▶ 変換開始')
        self.status_var.set(f'完了: {success}/{total} 件成功')
        if errors:
            messagebox.showwarning('変換完了（一部エラー）',
                f'{success}/{total} 件成功\n\nエラー:\n' + '\n\n'.join(errors))
        else:
            out = self._outdir or '各ファイルと同じフォルダ'
            messagebox.showinfo('変換完了',
                f'{success}/{total} 件の変換が完了しました！\n\n出力先: {out}')


if __name__ == '__main__':
    app = ConverterApp()
    app.mainloop()
