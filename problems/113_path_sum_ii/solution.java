/**
 * Definition for a binary tree node.
 * public class TreeNode {
 *     int val;
 *     TreeNode left;
 *     TreeNode right;
 *     TreeNode() {}
 *     TreeNode(int val) { this.val = val; }
 *     TreeNode(int val, TreeNode left, TreeNode right) {
 *         this.val = val;
 *         this.left = left;
 *         this.right = right;
 *     }
 * }
 */
class Solution {
    void solve(TreeNode root,int sum,List<Integer> temp, List<List<Integer>> ans,int targetSum){
        if(root==null) return;
        sum+=root.val;
        temp.add(root.val);
        if(root.left==null && root.right==null){
            if(sum==targetSum){
                ans.add(new ArrayList<>(temp));
            }
            temp.remove(temp.size()-1);
            return;
        }
        solve(root.left,sum,temp,ans,targetSum);
        solve(root.right,sum,temp,ans,targetSum);
        temp.remove(temp.size()-1);
        return;
    }
    public List<List<Integer>> pathSum(TreeNode root, int targetSum) {
        List<List<Integer>> ans=new ArrayList<>();
        if(root==null) return ans;
        int sum=0;
        List<Integer> temp=new ArrayList<>();
        solve(root,sum,temp,ans,targetSum);
        return ans;
    }
}